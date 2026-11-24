import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Phần lớn test gọi thẳng `cli.main` để kiểm TOÁN CỦA TỪNG VERB, không phải quy trình duyệt cổng, nên chốt chặn của CLI
# (cong.kiem_cong) mặc định được tắt trong test. Test nào đánh dấu `@pytest.mark.cong_that`
# (hoặc `pytestmark = pytest.mark.cong_that`) chạy với chốt THẬT. Chỉ patch ở chỗ CLI gọi `cong.kiem_cong`;
# MCP (mcp_server.kiem_cong, đã import tên) vẫn là bản thật.
# Patch cấp PHIÊN (không phải từng test) vì fixture cấp module/lớp cũng chạy `cli.main` trước fixture cấp hàm.
_THAT = {"bat": False}


@pytest.fixture(scope="session", autouse=True)
def _cli_chot_cong_theo_marker():
    from sannen import cong
    that = cong.kiem_cong
    cong.kiem_cong = lambda lot, verb, preview: that(lot, verb, preview) if _THAT["bat"] else (True, "")
    yield
    cong.kiem_cong = that


@pytest.fixture(autouse=True)
def _bat_chot_that_neu_co_marker(request):
    _THAT["bat"] = request.node.get_closest_marker("cong_that") is not None
    yield
    _THAT["bat"] = False


def pytest_configure(config):
    config.addinivalue_line("markers", "cong_that: chạy với chốt chặn cổng THẬT của CLI (mặc định tắt trong test)")
