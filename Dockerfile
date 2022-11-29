FROM python:3.9-alpine



RUN echo "http://dl-cdn.alpinelinux.org/alpine/edge/community" > /etc/apk/repositories
RUN echo "http://dl-cdn.alpinelinux.org/alpine/edge/main" >> /etc/apk/repositories

RUN apk update && apk add \
    xvfb \
    chromium \ 
    chromium-chromedriver 

# Install dependencies
RUN pip install --upgrade pip

COPY *.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

ENV DEBUG=false

EXPOSE 8080

VOLUME /profile

# Run the application
CMD ["python", "server.py"]