import io
from gevent.pywsgi import WSGIServer
from flask import request
import datetime as dt
from prometheus_client import start_wsgi_server, Summary, Counter
from multiprocessing import Process

# Create a metric to track time spent and requests made.
INF_LAG_NAME_FMT = 'inflag{}'
INF_LAG_DESC_FMT = 'Time spent processing request for INF {}'
INF_COUNTER_NAME_FMT = 'infcounter{}'
INF_COUNTER_DESC_FMT = 'Counter of requests processed for INF {}'

from libpycommon.utils.wx_login_utils import LoginUtils
from libpycommon.utils.wx_decrypt_utils import WXBizDataDecryptUtils
from libpycommon.utils.wx_QRcode_utils import WXAccessTokenUtils, WXQRCodeUtils
from libpycommon.common import mylog
from libadsusertestsys.common.utils import *
from libadsusertestsys.entity.evaluation_entity import ResponseData, UserGrade, get_internal_error_catched, get_internal_error_catched_user_req
from libadsusertestsys.dao.evaluation_dao import on_create_user, get_user_by_openid, update_user_phone_number, update_user_info, get_last_test_result, get_last_test_result_grouped, get_test_user_count
from libadsusertestsys.entity.evaluation_entity import TestOrientation, TestType
from libadsusertestsys.orm.config import *

APPID = misc.get_env_encrypted('APPID', package_key_res_path)
APPSECRET = misc.get_env_encrypted('APPSECRET', package_key_res_path)

BASE_FAKE_USER_NUMBER = 30000
BASE_FAKE_USER_DATE = dt.datetime.strptime("2021-3-20", "%Y-%m-%d")
BASE_FAKE_USER_INCREASE_BY_MINUTE = 0.1  # 每分钟增加人数


def serve_forever(app, myver):
    def _route_2_name(route):
        return route.replace('/', '_')

    def _get_metrics_summary(route):
        return Summary(INF_LAG_NAME_FMT.format(_route_2_name(route)), INF_LAG_DESC_FMT.format(_route_2_name(route)))

    def _get_metrics_counter(route):
        return Counter(INF_COUNTER_NAME_FMT.format(_route_2_name(route)), INF_COUNTER_DESC_FMT.format(_route_2_name(route)))

    @app.route("/", methods=["GET"])
    def ver():
        return get_serv_ver(myver)

    @app.route("/set/log", methods=["GET"])
    def set_loglevel():
        request_data = request_parse(request)
        return get_serv_set_loglevel(request_data)

    INF_ROUTE_get_wx_login = "/get/wx/login"
    INF_LAG_get_wx_login = _get_metrics_summary(INF_ROUTE_get_wx_login)
    INF_COUNTER_get_wx_login = _get_metrics_counter(INF_ROUTE_get_wx_login)
    @app.route(INF_ROUTE_get_wx_login, methods=["GET"])
    #@INF_LAG_get_wx_login.time()
    def get_wx_login_certification():
        #INF_COUNTER_get_wx_login.inc()
        request_data = request_parse(request)
        jscode = request_data.get("jscode")
        inviter_openid = request_data.get("inviter_openid")
        def _req_fn(jscode, inviter_openid):
            util = LoginUtils(APPID, APPSECRET, jscode)
            openid, session_key = util.get_openid_and_sessionkey()
            def _req_fn_user_req(openid, session_key, inviter_openid):
                login_result = on_create_user(openid=openid, session_key=session_key, inviter_openid=inviter_openid)
                code = 0 if login_result == 1 else 1001
                d_data_2deco = {
                    "session_key": session_key,
                    'inviter_openid': inviter_openid
                }
                rspdata = ResponseData(openid)
                return rspdata.get_d_decoed_yat(d_data_2deco).get_serv_resp(code)
            return get_internal_error_catched_user_req(openid, _req_fn_user_req, session_key, inviter_openid)
        return get_internal_error_catched({}, _req_fn, jscode, inviter_openid)

    '''
    测试样例
    {
        "openid": "o43Xk5P5oBPTcUkcKpRLoVeSb2e8",
        "session_key": "CmHlXStyOazZ5PdcZ5n0qw==",
        "iv": "kXPQt5l1ER2vHBZoOyCirA==",
        "encrypted_data": "PdSxJoJ5LCQHGND6s5SV7GVkvR5+Tdl6y4E60DzrKU20fUlvGW1uhH/nC2M63FbutqPrMJp7okaqwtDYSwoUbX2vDTHr9M2YwQbmOvnYnDuvN36NWeXN2zWCxiRY9LgfFjzQZ5fLp9PikFgVoMbsu2vd/9hsywNrJITjtSco3I2vMwQ21oZ2r0fZFQOZmeNnLA0vUT5oGhkr5kP80HKNrQ=="
    }
    '''
    INF_ROUTE_get_wx_decrypted = "/get/wx/decrypted"
    INF_LAG_get_wx_decrypted = _get_metrics_summary(INF_ROUTE_get_wx_decrypted)
    INF_COUNTER_get_wx_decrypted = _get_metrics_counter(INF_ROUTE_get_wx_decrypted)
    @app.route(INF_ROUTE_get_wx_decrypted, methods=["POST"])
    #@INF_LAG_get_wx_decrypted.time()
    def get_wx_decrypted_info():
        #INF_COUNTER_get_wx_decrypted.inc()
        request_data = request_parse(request, "json")
        session_key = request_data["session_key"]
        openid = request_data["openid"]
        iv = request_data["iv"]
        encrypted_data = request_data["encrypted_data"]
        def _req_fn(session_key, openid, iv, encrypted_data):
            util = WXBizDataDecryptUtils(APPID, session_key)
            decrypted_data = util.decrypt(encrypted_data, iv)
            phone_number = decrypted_data["phoneNumber"]
            update_user_phone_number(openid=openid, phone_number=phone_number)
            d_data = {
                "session_key": session_key,
                "decrypted_data": decrypted_data
            }
            rspdata = ResponseData(openid)
            return rspdata.get_d_decoed_yat(d_data).get_serv_resp()
        return get_internal_error_catched({}, _req_fn, session_key, openid, iv, encrypted_data)

    INF_ROUTE_get_wx_qrcode = "/get/wx/qrcode"
    INF_LAG_get_wx_qrcode = _get_metrics_summary(INF_ROUTE_get_wx_qrcode)
    INF_COUNTER_get_wx_qrcode = _get_metrics_counter(INF_ROUTE_get_wx_qrcode)
    @app.route(INF_ROUTE_get_wx_qrcode, methods=["POST"])
    #@INF_LAG_get_wx_qrcode.time()
    def get_wx_qrcode():
        #INF_COUNTER_get_wx_qrcode.inc()
        request_data = request_parse(request, "json")
        path = request_data["path"]
        width = request_data["width"]
        def _req_fn(path, width):
            access_token_util = WXAccessTokenUtils(APPID, APPSECRET)
            access_token = access_token_util.get_access_code()
            if access_token == "500":
                message = "unable to get access token"
                response = make_response(jsonify({"error": message}))
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response

            qrcode_util = WXQRCodeUtils(access_token, path, width)
            qrcode = qrcode_util.get_qr_code()
            if qrcode == "500":
                message = "unable to get qr code"
                response = make_response(jsonify({"error": message}))
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response

            if not os.path.exists(QRCODE_ABSPATH_ROOT):
                os.makedirs(QRCODE_ABSPATH_ROOT)

            filename = os.path.join(QRCODE_ABSPATH_ROOT, "{}_{}_{}.jpg".format(
                    APPID, width, path.replace("/", "_").replace("?", "_")))
            target_file = io.BytesIO(qrcode)

            def send_chunk():  # 流式读取
                while True:
                    chunk = target_file.read(FILE_DL_SIZE)
                    if not chunk:
                        break
                    yield chunk

            from flask import Response
            response = Response(send_chunk(), content_type='application/octet-stream')
            response.headers["Content-disposition"] = 'attachment; filename=%s' % filename
            # response.headers['Access-Control-Allow-Origin'] = '*'
            return response

        return get_internal_error_catched({}, _req_fn, path, width)

    INF_ROUTE_get_app_login = "/get/app/login"
    INF_LAG_get_app_login = _get_metrics_summary(INF_ROUTE_get_app_login)
    INF_COUNTER_get_app_login = _get_metrics_counter(INF_ROUTE_get_app_login)
    @app.route(INF_ROUTE_get_app_login, methods=["GET"])
    #@INF_LAG_get_app_login.time()
    def get_app_login_certification():
        #INF_COUNTER_get_app_login.inc()
        request_data = request_parse(request)
        openid = request_data.get("openid")
        inviter_openid = request_data.get("inviter_openid")
        def _req_fn_user_req(openid, inviter_openid):
            login_result = on_create_user(openid=openid, inviter_openid=inviter_openid)
            code = 0 if login_result == 1 else 1001
            d_data_2deco = {} if code != 0 else {
                'inviter_openid': inviter_openid
            }
            rspdata = ResponseData(openid)
            return rspdata.get_d_decoed_yat(d_data_2deco).get_serv_resp(code)
        return get_internal_error_catched_user_req(openid, _req_fn_user_req, inviter_openid)

    INF_ROUTE_get_user_info = "/get/user/info"
    INF_LAG_get_user_info = _get_metrics_summary(INF_ROUTE_get_user_info)
    INF_COUNTER_get_user_info = _get_metrics_counter(INF_ROUTE_get_user_info)
    @app.route(INF_ROUTE_get_user_info, methods=["GET"])
    #@INF_LAG_get_user_info.time()
    def get_test_user_info():
        #INF_COUNTER_get_user_info.inc()
        request_data = request_parse(request)
        openid = request_data.get("openid")
        def _req_fn_user_req(openid):
            test_user = get_user_by_openid(openid)
            code = 0
            d_data_2deco = {}
            if test_user is None:
                mylog.logger.warn("Warning! User not exist with openid {}!!!".format(openid))
                code = 1002
            else:
                result = {}
                result['age'] = misc.get_emptystr_if_none(test_user.age)
                result['phone_number'] = misc.get_emptystr_if_none(test_user.phone_number)
                result['uid'] = misc.get_emptystr_if_none(test_user.uid)
                grade_name = UserGrade(test_user.grade).name if test_user.grade is not None else ''
                result['grade'] = grade_name
                d_data_2deco['result'] = result
            rspdata = ResponseData(openid)
            return rspdata.get_d_decoed_yat(d_data_2deco).get_serv_resp(code)
        return get_internal_error_catched_user_req(openid, _req_fn_user_req)

    INF_ROUTE_set_user_info = "/set/user/info"
    INF_LAG_set_user_info = _get_metrics_summary(INF_ROUTE_set_user_info)
    INF_COUNTER_set_user_info = _get_metrics_counter(INF_ROUTE_set_user_info)
    @app.route(INF_ROUTE_set_user_info, methods=["POST"])
    #@INF_LAG_set_user_info.time()
    def set_test_user_info():
        #INF_COUNTER_set_user_info.inc()
        request_data = request_parse(request, "json")
        openid = request_data.get("openid")
        age = request_data.get("age")
        phone_number = request_data.get("phone_number")
        uid = request_data.get("uid")
        mylog.logger.debug("uid data type:{}".format(type(uid)))
        grade_str = request_data.get("grade")
        def _req_fn_user_req(openid, age, phone_number, uid, grade_str):
            grade = UserGrade.__dict__.get(grade_str) if grade_str is not None else None
            code = 0
            d_data_2deco = {}
            test_user = get_user_by_openid(openid)
            if test_user is None:
                mylog.logger.warn("Warning! User not exist with openid {}!!!".format(openid))
                code = 1002
            else:
                mylog.logger.debug("uid data type:{}".format(type(uid)))
                update_user_info(test_user, age=age, phone_number=phone_number, uid=uid, grade=None if grade is None else grade.value)
                result = {}
                if age is not None:
                    result['age'] = 1
                if phone_number is not None:
                    result['phone_number'] = 1
                if uid is not None:
                    result['uid'] = 1
                if grade is not None:
                    result['grade'] = 1
                d_data_2deco['result'] = result
            rspdata = ResponseData(openid)
            return rspdata.get_d_decoed_yat(d_data_2deco).get_serv_resp(code)
        return get_internal_error_catched_user_req(openid, _req_fn_user_req, age, phone_number, uid, grade_str)

    INF_ROUTE_get_user_last_test_result = "/get/user/last/test/result"
    INF_LAG_get_user_last_test_result = _get_metrics_summary(INF_ROUTE_get_user_last_test_result)
    INF_COUNTER_get_user_last_test_result = _get_metrics_counter(INF_ROUTE_get_user_last_test_result)
    @app.route(INF_ROUTE_get_user_last_test_result, methods=["GET"])
    #@INF_LAG_get_user_last_test_result.time()
    def get_user_last_test_result():
        #INF_COUNTER_get_user_last_test_result.inc()
        request_data = request_parse(request)
        openid = request_data.get("openid")
        test_type_str = request_data.get("test_type")
        def _req_fn_user_req(openid, test_type_str):
            code = 0
            d_data_2deco = {}
            user = get_user_by_openid(openid)
            if user is None:
                mylog.logger.warn("Warning! User not exist with openid {}!!!".format(openid))
                code = 1002
            else:
                test_result = get_last_test_result(user.id, test_type_str, TestOrientation.PLACEMENT_TEST.value)
                if test_result is not None:
                    d_data_2deco['test_type'] = test_type_str
                    d_data_2deco['score'] = test_result.score
                    d_data_2deco['level'] = test_result.acadsoc_level
                    d_data_2deco['rate_of_beaten'] = test_result.rate_of_beaten
                    d_data_2deco['create_time'] = test_result.create_time
            rspdata = ResponseData(openid)
            return rspdata.get_d_decoed_yat(d_data_2deco).get_serv_resp(code)
        return get_internal_error_catched_user_req(openid, _req_fn_user_req, test_type_str)

    INF_ROUTE_get_all = "/get/all"
    INF_LAG_get_all = _get_metrics_summary(INF_ROUTE_get_all)
    INF_COUNTER_get_all = _get_metrics_counter(INF_ROUTE_get_all)
    @app.route(INF_ROUTE_get_all, methods=["GET"])
    #@INF_LAG_get_all.time()
    def get_total():
        #INF_COUNTER_get_all.inc()
        user_number = get_test_user_count()
        if BOOL_FAKE_SWITCH:
            now = dt.datetime.now()
            delta_time_on_minute = ((now - BASE_FAKE_USER_DATE).total_seconds()) / 60
            fake_user_number = int(delta_time_on_minute * BASE_FAKE_USER_INCREASE_BY_MINUTE) + BASE_FAKE_USER_NUMBER
            if user_number < fake_user_number:
                user_number = fake_user_number
        d_data = {
            "total_user_number": user_number
        }
        return get_serv_resp(d_data)

    INF_ROUTE_get_user_test_summary = "/get/user/test/summary"
    INF_LAG_get_user_test_summary = _get_metrics_summary(INF_ROUTE_get_user_test_summary)
    INF_COUNTER_get_user_test_summary = _get_metrics_counter(INF_ROUTE_get_user_test_summary)
    @app.route(INF_ROUTE_get_user_test_summary, methods=["GET"])
    #@INF_LAG_get_user_test_summary.time()
    def get_user_test_summary():
        #INF_COUNTER_get_user_test_summary.inc()
        request_data = request_parse(request)
        openid = request_data.get("openid")
        def _req_fn_user_req(openid):
            code = 0
            d_data_2deco = {}
            user = get_user_by_openid(openid)
            if user is None:
                mylog.logger.warn("Warning! User not exist with openid {}!!!".format(openid))
                code = 1002
            else:
                test_result_grouped = get_last_test_result_grouped(user.id)
                if test_result_grouped is not None:
                    level_cnt, level_sum = 0, 0
                    l = [ test_result for test_result in test_result_grouped]
                    for test_result in l:
                        if test_result.acadsoc_level is not None:
                            d_data_2deco[test_result.test_type] = test_result.acadsoc_level
                            level_cnt += 1
                            level_sum += test_result.acadsoc_level
                    if level_cnt == 5:
                        level = round(level_sum/level_cnt)
                        d_data_2deco['level'] = level
                    d_data_2deco = {"last": d_data_2deco}
            rspdata = ResponseData(openid)
            return rspdata.get_d_decoed_yat(d_data_2deco).get_serv_resp(code)
        return get_internal_error_catched_user_req(openid, _req_fn_user_req)


def entry(port, myver):
    # Start up the server to expose the metrics.
    METRICS_PORT = int(misc.get_env('METRICS_PORT', '8090'))
    bind_addr = '0.0.0.0'
    #start_wsgi_server(METRICS_PORT, addr=bind_addr)

    INTERFACE_PORT = int(misc.get_env('INTERFACE_PORT', port))

    from libadsusertestsys.orm.user_test_sys_orm import app
    serve_forever(app, myver)
    wsgi_server = WSGIServer((bind_addr, INTERFACE_PORT), app)
    wsgi_server.serve_forever()
    '''
    for i in range(2):
        wsgi_server = WSGIServer((bind_addr, INTERFACE_PORT+i), app)
        p = Process(target=wsgi_server.serve_forever())
        p.start()
    '''

