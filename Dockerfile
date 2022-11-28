FROM python:3.7

# Install dependencies
RUN pip install --upgrade pip

COPY *.py .
COPY requirements.txt .

RUN pip install -r requirements.txt
RUN pip install gradio

EXPOSE 8080

VOLUME /profile

# Run the application
CMD ["python", "server.py"]