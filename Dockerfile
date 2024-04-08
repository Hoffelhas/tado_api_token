# Use an official Python runtime as a parent image
FROM python:3.12

# Obtain the files from Github
RUN mkdir /tado_api_token
RUN git clone https://github.com/Hoffelhas/tado_api_token /tado_api_token

# Set the working directory in the container
WORKDIR /tado_api_token
RUN cd /tado_api_token

# Install any needed dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run script.py when the container launches
CMD ["python", "-u", "refresh_tado_api_token.py"]
