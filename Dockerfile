FROM harbor.my.org:1080/base/py/usertestsys

ADD evaluation /data1/www/evaluation
ADD *.py /data1/www/
ADD requirements.txt /data1/www
ENV SERV_NAME usertestsys-general

RUN pip install --trusted-host pypi.my.org -r requirements.txt

CMD ["python","main.py", "8080"]
