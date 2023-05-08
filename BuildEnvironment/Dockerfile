FROM androidsdk/android-30:latest

# Install tools and JDK
RUN apt-get update \
	&& apt-get install -y \
	libgl1-mesa-dev \
	wget \
	unzip \
	openjdk-8-jdk \
	ffmpeg\
	python3-pip\
	git

# Install conda
RUN wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /anaconda.sh \
	&& bash /anaconda.sh -b -p /opt/conda \
    && rm /anaconda.sh
ENV PATH=$PATH:/opt/conda/bin
RUN conda create -n ReproBot python==3.7

# download the system images
# RUN for version in 19 21 23 24 26 28 29 30; do yes | sdkmanager "system-images;android-${version};google_apis;x86"; done

# Use conda to build python environment
ADD requirements.txt requirements.txt
RUN conda run --no-capture-output -n ReproBot pip install -r requirements.txt
RUN conda run --no-capture-output -n ReproBot python -m spacy download en_core_web_lg

CMD echo "Environment is ready"