import sys

import evaluation.service.evaluation_service as evaluation_service
from libadsusertestsys.common.utils import set_log_level_from_env


if __name__ == "__main__":
    set_log_level_from_env()

    port = sys.argv[1]
    from _version import __version__
    evaluation_service.entry(port, __version__)
