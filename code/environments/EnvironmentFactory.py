class EnvironmentFactory:
    @staticmethod
    def get_environment(config):
        """
        Factory method to return an instance of the appropriate environment
        based on the environment_name field defined in config.json.
        """
        if config.environment_name == "gym":
            from environments.EnvironmentGym import EnvironmentGym
            return EnvironmentGym(config)
        elif config.environment_name == "fisico":
            from environments.EnvironmentPhysical import EnvironmentPhysical
            return EnvironmentPhysical(config)
        else:
            raise ValueError(f"Environment '{config.environment_name}' is not recognized.")
