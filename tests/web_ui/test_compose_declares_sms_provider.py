"""合并之后测试机还得起得来：SMS fail-fast 闸拒绝空 KATRAIN_SMS_PROVIDER 启动。

⚠️ 这三条只守**仓库根**的 docker-compose.yml —— 那份只服务测试机（home-ubuntu）。
生产（ucloud）读的是 release 分支独有的 deploy/ucloud/compose.yml + /etc/katrain/ucloud.env，
develop 的 deploy/ 下只有 minio/，本仓拿不到那半操作数 ⇒ 生产那一半不可能由任何本仓测试证明，
只能靠部署时在容器上回显 env 的实测取证。**不要把这三条的绿读成「两台都配好了」。**

katrain-cron 不需要这个变量：Dockerfile.cron 只 `COPY katrain/cron/`，容器里根本没有
katrain/web/server.py，那条 lifespan 不会跑。哪天 Dockerfile.cron 改成 `COPY . /app`，
cron 也得配上，否则它会跟着拒绝启动。

变异验证（2026-09-11 实跑，三条各红且只红该红的那几条）：
  M1 删掉 compose 里 KATRAIN_SMS_PROVIDER 那一行
     → test_web_service_declares_the_sms_provider_env + test_it_fails_loudly... 红
  M2 把那行的 `:?` 改成 `:-aliyun`
     → 只 test_it_fails_loudly_instead_of_defaulting_to_empty 红
  M3 config.py 的 os.getenv 字面量改成 "KATRAIN_SMS_VENDOR"
     → 只 test_the_env_name_matches_what_config_actually_reads 红
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ENV_NAME = "KATRAIN_SMS_PROVIDER"


def _web_env() -> list:
    doc = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    return list(doc["services"]["katrain-web"]["environment"])


def test_web_service_declares_the_sms_provider_env():
    names = [str(e).split("=", 1)[0] for e in _web_env()]
    assert ENV_NAME in names, (
        f"docker-compose.yml 的 katrain-web 没有 {ENV_NAME} —— "
        "合并后这台机器会在 _lifespan_server 的闸上拒绝启动"
    )


def test_it_fails_loudly_instead_of_defaulting_to_empty():
    """用 `${VAR:?...}`：compose 当场拒绝，比把空串喂进闸再在 lifespan 里抛更早、话更清楚。

    写成 `${VAR:-}` 的话容器会带着空 provider 起来 —— 那正是闸要挡的状态，
    等于把 fail-fast 推迟到应用层，日志里只剩一条 traceback。
    """
    line = next(str(e) for e in _web_env() if str(e).split("=", 1)[0] == ENV_NAME)
    assert ":?" in line, f"{ENV_NAME} 必须写成 ${{{ENV_NAME}:?...}} 形式，实际是：{line}"


def test_the_env_name_matches_what_config_actually_reads():
    """闸只看得见字面量：compose 写一个名字、config.py 读另一个名字，两边各自都「对」。"""
    src = (REPO / "katrain/web/core/config.py").read_text(encoding="utf-8")
    assert re.search(rf"os\.getenv\(\s*[\"']{ENV_NAME}[\"']", src), (
        f"config.py 没有从 {ENV_NAME} 读 —— compose 里配了也白配"
    )
