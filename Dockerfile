RUN apt-get update && apt-get install -y wget gnupg curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g playwright \
    && playwright install