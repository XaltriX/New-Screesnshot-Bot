# Use an official Python runtime as a base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install ffmpeg for moviepy (optional, but recommended)
RUN apt-get update && apt-get install -y ffmpeg

# Expose the port the app will run on
EXPOSE 5000

# Run the bot script
CMD ["python", "bot.py"]
