import re
import time
import types
import traceback
from experiment.Experiment import Experiment


class CreateStrategyCompareUpdate(Experiment):
    """
    Iterative Policy Refinement experiment adapted for the physical
    differential-drive line-following robot.
    """

    def __init__(self, name, json_config_file="", base_dir="", results_path=""):
        super().__init__(name, json_config_file, base_dir, results_path)

        self.logger.log_to_console = True

        # Task, sensor, and differential-drive kinematics description
        self.task_description = """Consider that you are embodied in the following agent and environment.

Agent: A differential-drive mobile robot with two actuated wheels (left and right) and two downward-facing infrared reflectance sensors (left sensor and right sensor) mounted at the front, spaced slightly wider than a black track line on a white floor.

Goal: Keep the black line centered between the two sensors while continuously moving forward along the track for up to 20 time steps (maximum cumulative reward = 20.0).

Observation state: A 2D vector [sensor_esq, sensor_dir] with binary reflectance values:
- sensor_esq: 0.0 (left sensor detects the black line) or 1.0 (left sensor detects the white floor);
- sensor_dir: 0.0 (right sensor detects the black line) or 1.0 (right sensor detects the white floor);
When both sensors read [1.0, 1.0], the robot is centered on the track (+1.0 reward). When the left sensor reads 0.0 ([0.0, 1.0]), the robot has drifted to the left of the track center (+0.2 reward). When the right sensor reads 0.0 ([1.0, 0.0]), the robot has drifted to the right of the track center (+0.2 reward). When both sensors read [0.0, 0.0], the robot is completely off-track (-1.0 reward).

Action: A 2D list [left_pwm, right_pwm] representing the motor commands applied to the left and right wheels.
- Allowed discrete command values for each wheel: ONLY -255 (backward) or 255 (forward). Do NOT use 0 (stopping is forbidden).
- Differential-drive kinematics: rotating both wheels forward moves the robot straight ahead; rotating both wheels backward reverses the robot; rotating the left wheel forward and the right wheel backward turns the robot to the right; rotating the left wheel backward and the right wheel forward turns the robot to the left.

Failure Conditions:
- The episode terminates early if both sensors read [0.0, 0.0] for two consecutive time steps.
- The episode terminates after 20 time steps.
"""

        self.trial_reward = []
        self.overall_strategy_reasoning = ""
        self.overall_strategy_code = ""
        self.overall_strategy_rules = ""
        self.examples = ""

        self.previous_overall_strategy_reasoning = ""
        self.previous_overall_strategy_code = ""
        self.previous_overall_strategy_rules = ""
        self.previous_examples = ""

        self.best_reward = None
        self.best_overall_strategy_reasoning = ""
        self.best_overall_strategy_code = ""
        self.best_overall_strategy_rules = ""
        self.best_examples = ""

        if not hasattr(self.get_config().experiment, "steps_memory"):
            setattr(self.get_config().experiment, "steps_memory", 15)

    def remove_thinking(self, input_string):
        pattern = r"<think>.*?</think>"
        return re.sub(pattern, "", input_string, flags=re.DOTALL)

    def create_overall_strategy_reasoning(self, debug=False):
        self.logger.info("### Getting overall strategy reasoning from the LLM...")
        reasoning_prompt = f"""
            The task description is: {self.task_description}

            Briefly reflect on what could be a possible overall strategy to succeed in this task. Create a set of a few IF-THEN-ELSE rules relating the observations to the action definition. Do not use any reference to previous actions or reverse actions. The action at each time step should be defined based only on the current observation and should be a list with two integers representing the command for the left and right motors, like [left_pwm, right_pwm], using ONLY -255 or 255 (never 0).
            """
        self.logger.info(reasoning_prompt)
        t0 = time.perf_counter()
        self.overall_strategy_reasoning = self.get_llm().send_single_prompt(reasoning_prompt)
        lat_llm = time.perf_counter() - t0
        self.logger.info(f"[LLM LATENCY - Initial Reasoning]: {lat_llm:.2f} s")
        self.logger.info(f"############## LLM Overall strategy reasoning\n{self.overall_strategy_reasoning}")

    def get_rules_from_reasoning(self):
        self.logger.info("### Getting overall strategy rules from the LLM...")
        rules_prompt = f"""
            The task description is: {self.task_description}

            Based on the following reasoning\n{self.overall_strategy_reasoning}

            Extract the IF-THEN-ELSE rules from the reasoning. Do not use any reference to previous actions or reverse actions. The action at each time step should be defined based only in the current observation and should be a list with two integers [left_pwm, right_pwm] using ONLY -255 or 255 (never 0). Your response should contain only the rules, no other explanation.
            """
        self.logger.info(rules_prompt)
        self.previous_overall_strategy_rules = self.overall_strategy_rules
        t0 = time.perf_counter()
        self.overall_strategy_rules = self.remove_thinking(self.get_llm().send_single_prompt(rules_prompt))
        lat_llm = time.perf_counter() - t0
        self.logger.info(f"[LLM LATENCY - Rule Extraction]: {lat_llm:.2f} s")
        self.logger.info(f"############## LLM Overall strategy rules\n{self.overall_strategy_rules}")

    def get_code_from_rules(self, trial_failed=False, add_mid="", add_end=""):
        prompt = f"""
            The task description is: {self.task_description}

            Here are a set of IF-THEN-ELSE rules for choosing the action based on the observation variables.

            {self.overall_strategy_rules}

            {add_mid}

        Represent these same rules in a function using python code. The signature of the function should be get_action(sensor_esq, sensor_dir), the inputs are the two observation values (0.0 or 1.0) and the function returns the action as a list of two integers ([255, 255], [255, -255], [-255, 255], or [-255, -255]) using the rules above. Explicitly write if/elif conditions for all four sensor states ([1.0, 1.0], [0.0, 1.0], [1.0, 0.0], and [0.0, 0.0]) before the final fallback return [255, 255]. Never return [0, 0] and do NOT use the 'or' keyword inside a return statement. Your response should contain only the function definition using python code. No other text or explanation, neither formatting characters, only plain python code.

            {add_end}
            """
        if trial_failed:
            prompt += "\nYour previous python code did not work. Make sure your response will have only functional python code. No other explanation.\n"
        else:
            self.previous_overall_strategy_code = self.overall_strategy_code
        self.logger.info(prompt)

        t0 = time.perf_counter()
        raw_code = self.get_llm().send_single_prompt(prompt, coder=True)
        lat_llm = time.perf_counter() - t0
        self.logger.info(f"[LLM LATENCY - Code Generation]: {lat_llm:.2f} s")

        # Extract and clean the generated Python function block
        raw_code = raw_code.replace("```python", "").replace("```", "")
        match = re.search(r"def get_action\(.*?\):.*", raw_code, re.DOTALL)
        if match:
            self.overall_strategy_code = match.group(0)
        else:
            self.overall_strategy_code = raw_code

        self.logger.info(f"############## LLM Overall strategy code \n{self.overall_strategy_code}")

    def update_overall_strategy_reasoning(self, failed_reasoning=False, trial_number=1, add_end=""):
        self.logger.info("########### Getting updated overall strategy from the LLM...")
        prompt = f"""
            The task description is:\n{self.task_description}

            {"" if trial_number < 2 else f"You already tried {trial_number} different strategies , and the sequence of rewards was: {self.trial_reward}"}

            Your current overall strategy was this one:\n{self.overall_strategy_rules}

            Your experience with this strategy was:\n{self.examples}
            """
        if trial_number > 1:
            prompt += f"""
               Your previous overall strategy was this one:\n{self.previous_overall_strategy_rules}
               Your experience with this strategy was:\n{self.previous_examples}
            """
            if self.overall_strategy_rules == self.best_overall_strategy_rules:
                prompt += "\nYour best strategy so far is the current strategy.\n"
            elif self.previous_overall_strategy_rules == self.best_overall_strategy_rules:
                prompt += "\nYour best strategy so far was the previous strategy.\n"
            else:
                prompt += f"""
                   Your best overall strategy so far was this one:\n{self.best_overall_strategy_rules}
                   Your experience with this strategy was:\n{self.best_examples}
                """
        prompt += f"""
            Briefly reflect on your recent experiences acting on the environment with different strategies, check if your assumptions were true and which one performed the best. Choose some observations and reflect if the action taken was correct for achieving your goal, and also if they produced the effect you expected. Based on your analysis, choose the most effective strategy and update the rules for keeping the robot centered on the line for longer. Feel free to create a new strategy from scratch if you feel your previous strategies did not work as you desired.

            {add_end}
            """
        if failed_reasoning:
            prompt += "\nConsider that your last reasoning failed to produce a valid action based on observations. Make sure that your rules will produce an action that is a list of two non-zero integers [-255 or 255, -255 or 255].\n"
        self.logger.info(prompt)
        self.previous_overall_strategy_reasoning = self.overall_strategy_reasoning
        t0 = time.perf_counter()
        self.overall_strategy_reasoning = self.get_llm().send_single_prompt(prompt)
        lat_llm = time.perf_counter() - t0
        self.logger.info(f"[LLM LATENCY - Update/Reflection]: {lat_llm:.2f} s")
        self.logger.info(f"############## LLM UPDATED Overall strategy reasoning\n{self.overall_strategy_reasoning}")

    def get_action_from_llm(self, observation):
        action = None
        sensor_esq, sensor_dir = observation[0], observation[1]

        print(f"\n[LIVE SENSORS] Left: {sensor_esq} | Right: {sensor_dir}")

        for count in range(10):
            try:
                action = get_action(sensor_esq, sensor_dir)
                break
            except Exception:
                trace = traceback.format_exc()
                self.logger.error(trace)
                self.update_overall_strategy_reasoning(
                    add_end=f"Your previous reasoning lead to a code that generated the following error: \n{trace}\n"
                )
                self.get_rules_from_reasoning()
                self.get_code_from_rules(
                    add_mid=f"Your previous code was \n{self.overall_strategy_code}\n But it generated the following execution error \n{trace}\n"
                )
                self.define_get_action(self.overall_strategy_code)

        # Validate the action returned by the generated function
        for count in range(10):
            if (
                action is None
                or type(action) not in (list, tuple)
                or len(action) != 2
                or (action[0] == 0 and action[1] == 0)
            ):
                self.update_overall_strategy_reasoning(
                    add_end=f"Your previous reasoning generated an invalid or stationary action {action}. Stopping [0, 0] is strictly forbidden! You MUST use only 255 or -255 for each wheel."
                )
                self.get_rules_from_reasoning()
                self.get_code_from_rules()
                self.define_get_action(self.overall_strategy_code)
                action = get_action(sensor_esq, sensor_dir)
            else:
                break

        if count == 10:
            exit(-1)

        return action

    def before_run_trial(self, trial_number):
        self.episode_sequence = []

        if trial_number == 0:
            self.create_overall_strategy_reasoning()
        else:
            if self.trial_reward[-1] < 20.0:
                self.update_overall_strategy_reasoning(trial_number=trial_number)
            else:
                self.logger.info("##### Last trial got max reward (20.0) #####")

        if len(self.trial_reward) == 0 or self.trial_reward[-1] < 20.0:
            self.get_rules_from_reasoning()
            self.get_code_from_rules()

        for i in range(10):
            try:
                self.define_get_action(self.overall_strategy_code)
                break
            except Exception as e:
                self.logger.error(f"Trial #{i} - Error: {str(e)}")
                self.get_code_from_rules(add_end=f"Your last code generated the following error:\n{str(e)}\n")

    def get_last_steps_history(self):
        history_size = len(self.episode_sequence)
        if history_size == 0:
            return "The trial is starting. There is no sequence of observations and actions yet."
        if history_size >= self.get_config().experiment.steps_memory:
            return "\n".join(self.episode_sequence[-self.get_config().experiment.steps_memory:])
        return "\n".join(self.episode_sequence)

    def after_run_trial(self, trial_number, trial_reward):
        obs_hist, act_hist = (
            self.get_data_manager()
            .get_last_trial_data()
            .get_last_steps_obs_action(self.get_config().experiment.steps_memory)
        )

        for i in range(len(obs_hist)):
            self.episode_sequence.append(
                f"\n{self.normalize_and_discretize(obs_hist[i])};{None if act_hist[i] is None else act_hist[i]}"
            )

        self.trial_reward.append(trial_reward)
        self.previous_examples = self.examples
        self.examples = f"""
            Last {self.get_config().experiment.steps_memory if len(self.episode_sequence) > int(self.get_config().experiment.steps_memory) else len(self.episode_sequence)} steps from a trial using this strategy. The average reward in {self.get_config().experiment.estimate_reward_trials} trials was {trial_reward}/20
                {self.get_last_steps_history()}
        """

        if self.best_reward is None or trial_reward >= self.best_reward:
            self.best_reward = trial_reward
            self.best_examples = self.examples
            self.best_overall_strategy_reasoning = self.overall_strategy_reasoning
            self.best_overall_strategy_code = self.overall_strategy_code
            self.best_overall_strategy_rules = self.overall_strategy_rules

    def define_get_action(self, func_str):
        exec(func_str, globals())
        self.get_action = types.MethodType(get_action, self)

    def before_step(self, step):
        pass

    def after_step(self, step):
        pass

    def normalize_and_discretize(self, observation):
        return observation
