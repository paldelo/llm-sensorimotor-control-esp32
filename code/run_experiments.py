import argparse
import os
import shutil
import warnings

from experiment.ExperimentSeries import ExperimentSeries

if os.name == 'nt':
    os.system('cls')
else:
    os.system('clear')

warnings.filterwarnings("ignore")

EXPERIMENTS_DIR = 'user_experiments'
CONFIG_FILENAME = 'config.json'

RESULTS_ROOT = 'results'
LOGS_DIR = 'logs'
VIDEO_DIR = 'videos'

parser = argparse.ArgumentParser(description="Run series of experiments")

parser.add_argument(
    '--name',
    type=str,
    required=True,
    help=f"Name of the experiment. It has to be equal to the folder name in {EXPERIMENTS_DIR}"
)
parser.add_argument('--delete_previous_data', action='store_true', help='Delete the previous data')
parser.add_argument('--append_results', action='store_true', help='Append to the previous result')

args = parser.parse_args()

experiment_folder = os.path.join(EXPERIMENTS_DIR, args.name)
config_file = os.path.join(experiment_folder, CONFIG_FILENAME)

if not os.path.exists(experiment_folder):
    print(f"Error: The experiment folder '{experiment_folder}' does not exist.")
    exit(1)

if not os.path.isfile(config_file):
    print(f"Error: The config file '{CONFIG_FILENAME}' is missing in '{experiment_folder}'.")
    exit(1)

results_path = os.path.join(RESULTS_ROOT, args.name)
logs_path = os.path.join(LOGS_DIR, args.name)
videos_path = os.path.join(VIDEO_DIR, args.name)

if (
    (os.path.exists(results_path) and any(os.scandir(results_path)))
    or (os.path.exists(logs_path) and any(os.scandir(logs_path)))
    or (os.path.exists(videos_path) and any(os.scandir(videos_path)))
):
    if args.delete_previous_data:
        while True:
            ans = input(f"ATTENTION: Are you sure you want to delete previous data from {args.name} experiment? (yes/no)")
            if ans.lower() not in ("yes", "no"):
                print("Write yes or no")
            else:
                if ans.lower() == "no":
                    exit("Aborting by user request.")
                else:
                    break
        print(f"One or more data directories '{results_path};{logs_path};{videos_path}' are not empty. Deleting it by user request (--delete_previous_data).")
        if args.name != "":
            if os.path.exists(results_path) and os.path.isdir(results_path):
                shutil.rmtree(results_path)
            if os.path.exists(logs_path) and os.path.isdir(logs_path):
                shutil.rmtree(logs_path)
            if os.path.exists(videos_path) and os.path.isdir(videos_path):
                shutil.rmtree(videos_path)
    else:
        if not args.append_results:
            print(f"Error: One or more data directories '{results_path};{logs_path};{videos_path}' are not empty. Please empty them before proceeding or use --delete_previous_data or --append_results.")
            exit(1)
        else:
            print("Appending results")

if not os.path.isdir(results_path):
    os.makedirs(results_path)
    print(f"The results directory '{results_path}' has been created.")

print(f"Running experiments for '{args.name}'...")
experiment_series = ExperimentSeries(config_file, results_path=results_path)
experiment_series.run_experiments()
