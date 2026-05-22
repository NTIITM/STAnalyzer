from setuptools import setup, find_packages

setup(
    name="system-server",
    version="1.0.0",
    description="系统服务管理和 API 服务器",
    author="textMSA Team",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pydantic>=2.0.0",
        "httpx>=0.24.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
    ],
    python_requires=">=3.8",
)

