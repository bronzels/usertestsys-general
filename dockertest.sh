docker login harbor.my.org:1080
docker rmi harbor.my.org:1080/base/py/usertestsys
docker pull harbor.my.org:1080/base/py/usertestsys
docker build ./ --add-host pypi.my.org:192.168.0.62 -t harbor.my.org:1080/python-app/usertestsys-general
docker push harbor.my.org:1080/python-app/usertestsys-general

docker run --rm --name usertestsys-general -p 8807:8080 -e PYTHONUNBUFFERED=1 -e DB_HOST=192.168.0.85 -e DB_DATABASE=AcadsocDataAnalysisAlgorithm -e DB_USER=sa -e DB_PASSWD=Aks@12345 -e REDIS_HOST=192.168.0.62 -e REDIS_PORT=16379 -e REDIS_PASSWD=12345 -e REDIS_MAX_CONN=10 -e XUNFEI_APPID=5f3b5c3c -e XUNFEI_APISECRET=54de07b55a2fe56cae8eb42166c9b94c -e XUNFEI_APIKEY=4e8c3e2b9244755a190c55febddcfe29 -e FILES_URL_PREFIX=http://192.168.0.85:21080 harbor.my.org:1080/python-app/usertestsys-general
docker stop usertestsys-general