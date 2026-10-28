"""Versioned public vocabulary. Registration describes shape, never truth.

The native contract is generated from this catalog. Extending it requires a
reviewed release; Agent-supplied schemas cannot register trusted facts.
"""
import re

VERSION = 'aevora.fact-catalog/1'
LEGACY_KEYS = frozenset('concurrency_scope worker_count worker_count_known shared_state_kind synchronization_scope transaction_guarantees observed_failure_mode shared_object_scope sqlite_journal_mode operation_semantics authority_model clock_domain failure_domain contract_version lease_expiry_semantics authority_validation supported_operation_set'.split())
NATIVE_PROPERTIES = {
    'runtime_revision': {'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.+~-]{0,127}$','description':'当前可信原生程序的源码版本标识；可将经验限定到受控核验覆盖的固定实现。'},
    'runtime_version': {'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.+~-]{0,79}$','description':'当前可信原生运行时的发行版本；经验可限定到实际验证的版本。'},
    'runtime_os': {'type': 'string', 'pattern': '^[a-z0-9_]{1,32}$', 'description': '当前原生程序的操作系统目标（Go GOOS）；不替代宿主或硬件诊断。'},
    'runtime_arch': {'type': 'string', 'pattern': '^[a-z0-9_]{1,32}$', 'description': '当前原生程序的运行架构（Go GOARCH）；不证明物理 CPU 或其他平台已验证。'},
    'runtime_engine': {'type': 'string', 'enum': ['go_native', 'python_reference'], 'description': '执行经验服务的运行时。'},
    'storage_backend': {'type': 'string', 'enum': ['sqlite', 'falkordb'], 'description': '当前项目配置的存储后端；不证明数据已恢复。'},
    'console_access': {'type': 'string', 'enum': ['loopback_read_only'], 'description': '原生 Console 的本机只读接入契约。'},
}
TARGET_PROPERTIES = {
    'target_project': {'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$','description':'受保护本地注册中的目标项目名称；不是 Host 身份或 Agent 自述。'},
    'target_revision': {'type':'string','pattern':'^[0-9a-f]{40}([0-9a-f]{24})?$','description':'任务建立时目标工作区 Git HEAD 的实测提交；不证明未提交文件、测试结果或因果收益。'},
    'target_branch': {'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_.+/@-]{0,127}$','description':'任务建立时目标工作区的 Git 分支；detached HEAD 时保持未知。'},
    'target_worktree_state': {'type':'string','enum':['CLEAN','DIRTY','CONFLICTED'],'description':'Git porcelain 状态的有界观察；不是所有文件内容的独立完整性证明。'},
    'target_worktree_snapshot': {'type':'string','pattern':'^[0-9a-f]{64}$','description':'Git 状态、暂存区差异和变化文件元数据的汇总；不公开路径或文件内容，不是内容证明。'},
    'target_dependency_snapshot': {'type':'string','pattern':'^[0-9a-f]{64}$','description':'已注册根和有界一级模块的固定依赖清单/锁文件汇总；不递归解析工作区或执行脚本，范围降级明确披露。'},
    'target_manifest_set': {'type':'string','pattern':'^[a-z]+(\\+[a-z]+)*$','description':'已观察根和一级模块的清单种类，不等于全部语言、依赖或实际安装版本；不同模块声明不同时单值版本保持未知。'},
    'target_go_requirement': {'type':'string','pattern':'^[0-9]+\\.[0-9]+(\\.[0-9]+)?$','description':'go.mod 声明的 go 指令；不是本机 Go 版本。'},
    'target_node_requirement': {'type':'string','pattern':'^[0-9.<>=|^~*+,! xX-]{1,80}$','description':'package.json 声明的 engines.node 版本范围；不是实际 Node 版本。'},
    'target_python_requirement': {'type':'string','pattern':'^[0-9.<>=|^~*+,! xX-]{1,80}$','description':'pyproject.toml 的 project.requires-python 声明；不是实际 Python 版本。'},
}
PUBLIC_FACT_KEYS = LEGACY_KEYS | NATIVE_PROPERTIES.keys() | TARGET_PROPERTIES.keys()


def catalog():
    properties = {key: {'type': ['string', 'number', 'boolean', 'null'],
                        'description': '既有公共条件；值和来源由可信 Host 独立建立。'}
                  for key in sorted(LEGACY_KEYS)}
    properties.update(NATIVE_PROPERTIES)
    properties.update(TARGET_PROPERTIES)
    return {'schema_version': VERSION,
            'registration': 'RELEASE_CONTROLLED_NOT_AGENT_DEFINED',
            'default_domain': 'concurrency',
            'domains': {
                'concurrency': {'fact_keys': sorted(LEGACY_KEYS), 'support_context_keys': ['concurrency_scope']},
                'native_runtime': {'fact_keys': sorted(NATIVE_PROPERTIES),
                                   'support_context_keys': ['runtime_engine', 'storage_backend']},
                'target_project': {'fact_keys': sorted(TARGET_PROPERTIES),
                                   'support_context_keys': ['target_project']}},
            'context_schema': {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                               'type': 'object', 'properties': properties,
                               'additionalProperties': False}}


def support_coverage(premise_keys):
    keys = set(premise_keys)
    domains = catalog()['domains']
    matched = [domain for domain in domains.values() if keys & set(domain['fact_keys'])]
    for domain in matched or [domains[catalog()['default_domain']]]:
        keys.update(domain['support_context_keys'])
    return keys


def valid_value(key, value):
    """Additional constraints for new domains; preserve legacy unknowns."""
    spec = NATIVE_PROPERTIES.get(key) or TARGET_PROPERTIES.get(key)
    if spec is None or value is None:
        return True
    if isinstance(value, str) and value.strip().lower().replace('-', '_').replace(' ', '_') in {
            'unknown', 'unavailable', 'unspecified', 'not_observed'}:
        return True
    if not isinstance(value, str):
        return False
    return (value in spec['enum'] if 'enum' in spec else re.fullmatch(spec['pattern'], value) is not None)
