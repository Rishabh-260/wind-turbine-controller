% Run deterministic controller scenarios and export CSV traces.
% Execute from the repository root with: run('matlab/run_scenarios.m')

clearvars;
close all;

outputDir = fullfile('artifacts', 'raw');
if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

dt = 0.02;
scenarios = {
    struct('name', 'tracking', 'duration_s', 40, ...
        'wind_fn', @(t) 10 + 3 * (t >= 5))
    struct('name', 'gust', 'duration_s', 50, ...
        'wind_fn', @(t) 11 + 3 * (t >= 25 && t < 30))
    struct('name', 'saturation', 'duration_s', 40, ...
        'wind_fn', @(t) 10 + 8 * (t >= 5 && t < 25))
};

for k = 1:numel(scenarios)
    scenario = scenarios{k};
    trace = simulate_scenario(scenario, dt);
    outputFile = fullfile(outputDir, [scenario.name, '.csv']);
    writetable(trace, outputFile);
    fprintf('Wrote %s (%d samples)\n', outputFile, height(trace));
end

function trace = simulate_scenario(scenario, dt)
    ratedSpeed = 12.0;      % rpm
    ratedWind = 12.0;       % m/s
    pitchEffect = 0.90;     % rpm per degree; intentionally simplified
    rotorTimeConstant = 2.5; % s
    proportionalGain = 3.0; % deg/rpm
    integralGain = 0.50;    % deg/(rpm*s)
    pitchMin = 0.0;         % deg
    pitchMax = 30.0;        % deg
    pitchRateMax = 8.0;     % deg/s

    time = (0:dt:scenario.duration_s)';
    sampleCount = numel(time);
    wind = zeros(sampleCount, 1);
    rotorSpeed = zeros(sampleCount, 1);
    pitchCommand = zeros(sampleCount, 1);
    pitchAngle = zeros(sampleCount, 1);
    integralError = 0.0;

    for i = 1:sampleCount
        wind(i) = scenario.wind_fn(time(i));
        freeRotorSpeed = ratedSpeed * (wind(i) / ratedWind)^3;

        if i == 1
            rotorSpeed(i) = freeRotorSpeed;
            continue;
        end

        errorRpm = rotorSpeed(i - 1) - ratedSpeed;
        candidateIntegral = integralError + errorRpm * dt;
        rawCommand = proportionalGain * errorRpm + integralGain * candidateIntegral;
        limitedCommand = min(max(rawCommand, pitchMin), pitchMax);

        % Conditional integration prevents the integral term winding up at a limit.
        pushingFurtherIntoLimit = (rawCommand > pitchMax && errorRpm > 0) || ...
            (rawCommand < pitchMin && errorRpm < 0);
        if ~pushingFurtherIntoLimit
            integralError = candidateIntegral;
            rawCommand = proportionalGain * errorRpm + integralGain * integralError;
            limitedCommand = min(max(rawCommand, pitchMin), pitchMax);
        end

        maxPitchChange = pitchRateMax * dt;
        pitchChange = min(max(limitedCommand - pitchAngle(i - 1), -maxPitchChange), maxPitchChange);
        pitchAngle(i) = pitchAngle(i - 1) + pitchChange;
        pitchCommand(i) = limitedCommand;

        speedDerivative = (freeRotorSpeed - pitchEffect * pitchAngle(i) - rotorSpeed(i - 1)) ...
            / rotorTimeConstant;
        rotorSpeed(i) = max(0, rotorSpeed(i - 1) + speedDerivative * dt);
    end

    % Record the held command at the initial sample for a complete trace.
    pitchCommand(1) = pitchAngle(1);
    trace = table(time, wind, rotorSpeed, repmat(ratedSpeed, sampleCount, 1), ...
        pitchCommand, pitchAngle, 'VariableNames', ...
        {'time_s', 'wind_mps', 'rotor_speed_rpm', 'rated_speed_rpm', ...
         'pitch_command_deg', 'pitch_angle_deg'});
end
