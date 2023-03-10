docker build -t robot-quick-start .
docker run --env-file .env -p 3001:3001 -it robot-quick-start
