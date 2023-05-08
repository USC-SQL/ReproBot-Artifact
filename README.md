# Automatically Reproducing Android Bug Reports Using Natural Language Processing and Reinforcement Learning
This is the artifact of paper Automatically Reproducing Android Bug Reports Using Natural
Language Processing and Reinforcement Learning accepted by ISSTA 2023. In this paper, we proposed a novel approach to automatically reproduce Android bug reports. Our approach leverages advanced natural language process techniques to holistically and accurately analyze a given bug report and adopts reinforcement learning to effectively reproduce it. We implemented the approach into a tool -- ReproBot. 

In the following, we first provide a quick running example for you to run ReproBot in [Getting Started](#getting-started). Then we show details to run ReproBot on our evaluation dataset and new subjects in [Detailed Description](#detailed-description).

## Getting Started
:exclamation::exclamation: There are files in this repository stored in Git Large File Storage. Please [install `git lfs`](https://docs.github.com/en/repositories/working-with-files/managing-large-files/installing-git-large-file-storage) and run `git lfs pull` to get these files after cloning the repo.

In this section, we provides a running example of ReproBot. Here, we show how to run ReproBot from provided Docker environment. This way won't show the UI of Android emulator. However, you could also set up environment on your host machine and run ReproBot with the UI of Android emulator. For details, please refer to instructions [here](#without-docker).
We will use `docker` and `docker-compose` command in the following tutorial. Please refer to [official instruction](https://docs.docker.com/get-docker/) for installation.
The example bug report that we used to illustrate the process is from [transistor#63](https://github.com/y20k/transistor/issues/63) and its associated files are stored in the "./TestInput" folder.
The following steps was tested using `docker` 20.10.8 and `docker-compose` 1.29.2 on a physical x86 Ubuntu 20.04 machine with eight 3.6GHz CPUs and 32G of memory.
Please make sure you have at least 40 GB on your machine's disk to run the following example.

### Step 1: Obtain docker image
To run ReproBot, we need two docker images. One is used to run ReproBot's main code. Another is to run an underlying tool the provides services that ReproBot needs.
First, run the following command in the "BuildEnvironment" folder to build the docker image using the [Dockerfile](./BuildEnvironment/Dockerfile). 
```bash
# Estimated Time: 18m. Note: depending on your network condition, this may take longger time to finish.
docker build -t reprobot ./  
```
Above command build an image with tag "reprobot". Besides, you also need to pull the image for the underlying tool, OpenIE 5, by running the following command:
```bash
# Estimated Time: 4m30s.
docker pull chengchingwen/openie
```
### Step 2: Start docker container
Next, we use `docker-compose` command to create containers for the images and start them. The configuration file is [docker-compose.yaml](./BuildEnvironment/docker-compose.yaml).
Specifically, run the following command in the "BuildEnvironment" directory to start the container. 
```bash
# Estimated Time: 4m.
export API_VERSION=23 && docker-compose up -d --force-recreate
```
This command will create and start both the reprobot container and the openie container. For the reprobot container, it will also create and start the Android emulator with the specified Android version. To explain, the first `export` command delares an environment variable, which tells the reprobot container which version of the Android emulator to create and start. In this tutorial, the example bug report is reported on Android 6 whose corresponding API level is 23. If you need to run other version of Android OS, please replace 23 with corresponding API level (you can find the corresponding API level for an Android version [here](https://commonsware.com/Jetpack/pages/chap-resourcetour-002.html).

Once the above command finished running, please use the command `docker ps` to see the status of started containers. Once both of their status show as "healthy", you can proceed to the next step.

### Step 3: Run ReproBot
Once all containers are started, you can run ReproBot in the container. First, you need to identify the id of the reprobot container id by running `docker ps` and go inside the container by running `docker exec -it {container_id} bash`.
This leads you to a bash interface where you can run commmands inside the container.
Then you can run ReproBot by the following commands:
```bash
# Estimated Time: 1m40s
conda init bash && source ~/.bashrc && conda activate ReproBot # start the Conda python environment
cp "/ReproBot/TestInput/setup_run.py" "/ReproBot/src/utils/setup_run.py" # update the setup script for the report under test
cd /ReproBot/src # jump to the source code directory 
python tool_main.py \
    --reportFile "../TestInput/report.txt" \
    --apkFile "../TestInput/app.apk" \
    --crashLog "../TestInput/error_message.txt" \
    --deviceId emulator-5554 \
    --adbPort 5554 \
    --outputDir "./output" \
    --openieIP "openie"
```
The last python command above runs ReproBot on the example bug report. It provides ReproBot with all the inputs files and args (please refer to [Input Arguments](#input-arguments) for details). The example bug report will be successfully reproduced within couple minutes. As a result, you will see an one line logging "Successfully reproduced!" appears. After the command finishes running, there will be a newly created folder "./output" containing the generated output of ReproBot (please refer to [Output Structure](#output-structure) for details).

## Detailed Description
This section provides detailed specifications of ReproBot and instructions to run ReproBot on the evaluation dataset.
### Evaluation Dataset
Our evaluation dataset has 77 subjects (i.e., Android bug report). [This sheet](./Evaluation/subjects.csv) shows the information of each subject. The meanings of columns are: 
* Bug Report ID: the id of a bug report, which can be used to find associated files in our dataset; 
* GitHub Issue Link: the link to the GitHub issue of the bug report; 
* Number of actual S2Rs: the number of actual steps to reproduce the bug report; 
* Number of reported S2Rs: the number of steps in the bug report; 
* SDK: the Android SDK version that the bug report is reproduced on.

You can download the dataset from [here](https://drive.google.com/drive/folders/1mnuU7m_1wxal3uGNxAeDV6i0hpTdrVo5?usp=sharing). Each subject includes a bug report (.txt), an app (.apk), an error message file (.txt) and a setup script file (.py). Specifically, the error message file containes the crash message for each bug report and the setup script file provides necessary setup steps for each app. The specific subfolders of the dataset is described below:
* APKs: the apk files for each subject. 
* BugReports: the bug report text for each subject. The bug reports are organized by android versions (Android X) which represents the platform that the crash is reproduced on.
* ErrorMessages: the crash message for each subject.
* SetupScripts: the setup script for each subject.

### ReproBot Specification
The source code of ReproBot is under "src" folder and the main driver of ReproBot is the "./src/tool_main.py" file. To run it, you can run `python tool_main.py` in the "src" folder with the input arguments as described below. 
#### Input Arguments
Here are the main arguments it takes to run ReproBot on a subject:
* --apkFile: the path to the apk file to be analyzed.
* --reportFile: the path to the bug report file to be analyzed.
* --crashLogFile: the path to the oracle file.
* --deviceId: the device ID of the Android emulator (you can obtain it by running `adb devices`).
* --adbPort: the adb port specified for the Android emulator, by default it's set to be 5554.
* --outputDir: the path where ReproBot can generate its output, by default it's set to be "./output".
* --openieIP: the IP address that OpenIE 5 server is on. On local machine, it by default is "localhost". In the provided docker container, it's set to be "openie".

#### Output Structure
In the output folder contains the following sub-folders:
* logcat: it contains the logs from Android emulator.
* logs: it contains the logs of ReproBot.
* nlp_output: it contains the generated reproduction steps ("s2rs-xxx.json") and other intermidiate files.
* rl_log: it contains the log files for the reinforcement learning.
* uiautomator_state: it contains the screenshots and view hierarchy of each steps during the exploration of the app.
* success_action_seq.json: it contains the UI events that found by ReproBot to reproduce the bug report (only exists when ReproBot successfully reproduced the report).

### Run ReproBot on Evaluation Subjects
> The detailed results used in our paper can be find [here](./Evaluation/results.csv). Please note that, since the second stage of ReproBot involves random exploration, each run of ReproBot may generate different results.
#### With Docker
To run a subject from our dataset, please first download [our dataset](#evaluation-dataset). Please replace the example files in "TestInput" with corresponding files of the desired subject (rename as well). Then follow the steps in [Getting Started](#getting-started) to run ReproBot on it.

#### Without Docker
If you want to set up all such on your local machine instead of using docker, first please follow the steps below to set up your local environment:
1. Install Java 1.8 or 11 and have it accessible from command line.
2. Install [Android SDK tools](https://guides.codepath.com/android/installing-android-sdk-tools) and have the `adb` command accessible from command line.
3. Install Python 3.7 and install the python dependencies in [requirements.txt](./BuildEnvironment/requirements.txt) by running `pip install -r requirements.txt` in the "BuildEnvironment" directory. 
4. Our tool uses Spacy for natural language process. Please install the language model needed by Spacy by running `python -m spacy download en_core_web_lg`.
5. Our tool use OpenIE5 to perform extraction from natural language sentences. In order to run OpenIE5, please first download its Docker image by running `docker pull chengchingwen/openie`. 

Before running ReproBot, there are two more things to do:
1. Start OpenIE5's container by running `docker run -d -p 8000:8000 chengchingwen/openie`. This will start OpenIE5's server and listen on localhost:8000. It may take couple miniutes (Please wait at least 2 minutes) to fully start. Once it started, you can verify this by running command `curl -X POST http://localhost:8000/getExtraction -d 'I like apple.'`. The expected return would be:
```txt
[{"confidence":0.45170382506656653,"sentence":"I like apple.","extraction":{"arg1":{"text":"I","offsets":[[0]]},"rel":{"text":"like","offsets":[[2,3,4,5]]},"arg2s":[{"text":"apple","offsets":[[7,8,9,10,11]]}],"context":null,"negated":false,"passive":false}}]
```
2. Create and start the corresponding Android emulator.
	* We suggest to use AndroidStudio to create the Android emulator. Please follow the [official instructions](https://developer.android.com/studio/run/managing-avds) for details.
	* After creating the Android emulator, you can start it either from [commandline](https://developer.android.com/studio/run/emulator-commandline) or using AndroidStudio.

Then you can run ReproBot following the [input specifications](#input-arguments).

### Run ReproBot on New Subjects
To run ReproBot on new subjects, you first need to prepare the required input files. For a new bug report, please prepare the following files:
1. Bug report file: a `.txt` file that contains the sentences of reproduction steps of a bug report. Please put each sentence in one line.
2. APK file: the APK file of the app that the report can be reproduced on.
3. Crash log file: a `.txt` file that contains a line of error message the will show up in Android device log (can be obtained from the output of `adb logcat`) when the crash is triggered.
4. Setup script file: if the reproduction of the bug report needs some setup steps, such as login or grating permission, please use UIAutomator scripts to specify them in this file. Please use the template provided [here](./Evaluation/template.py) to create this script (only need to add scripts in the `run` method).

These steps create the files in the "TestInput" folder. Once you finish above steps, you can replace the files in the "TestInput" folder with the new subject's files and following the steps in [Getting Started](#getting-started) to run ReproBot on it.
