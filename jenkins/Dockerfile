FROM jenkins/jenkins:lts

USER root

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    qemu-system-arm \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Установка Chrome для Selenium
RUN apt-get update && apt-get install -y wget
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

# Установка chromedriver соответствующей версии Chrome
RUN CHROME_VER=$(google-chrome --version | sed -E 's/.* ([0-9]+)\..*/\1/') \
    && echo "Detected Chrome major version: ${CHROME_VER}" \
    && CHROMEDRIVER_VERSION=$(curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VER}) \
    && echo "Installing chromedriver version: ${CHROMEDRIVER_VERSION}" \
    && wget -q http://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip -d /usr/local/bin/ \
    && rm chromedriver_linux64.zip \
    && chmod +x /usr/local/bin/chromedriver || true

USER jenkins
