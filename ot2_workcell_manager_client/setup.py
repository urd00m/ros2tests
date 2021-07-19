from setuptools import setup

package_name = "ot2_workcell_manager_client"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="nerra",
    maintainer_email="alan.linghao.wang@gmail.com",
    description="TODO: Package description",
    license="TODO: License declaration",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "retry_api = ot2_workcell_manager_client.retry_api:main_null",
            "register_api = ot2_workcell_manager_client.register_api:main_null",
            "worker_info_api = ot2_workcell_manager_client.worker_info_api:main_null",
        ],
    },
)
