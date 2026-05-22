# 快速开始：离线模式设置

## 步骤 1：下载基因集库文件

```bash
cd /home/common/hwluo/project/system_server/services/gene-enrichment-analysis

# 下载常用的基因集库（推荐）
python download_enrichr_libraries.py

# 或者只下载最常用的几个库
python download_enrichr_libraries.py --libraries \
    GO_Biological_Process_2021 \
    KEGG_2021_Human \
    GO_Cellular_Component_2021 \
    GO_Molecular_Function_2021
```

下载完成后，文件会保存在 `./gmt/` 目录下。

## 步骤 2：配置服务使用本地文件

### 方法 1：使用环境变量（推荐）

```bash
export USE_LOCAL_GMT=true
export GMT_DIR=/home/common/hwluo/project/system_server/services/gene-enrichment-analysis/gmt
```

### 方法 2：修改 docker-compose.yml

在 `docker-compose.yml` 中添加：

```yaml
environment:
  - USE_LOCAL_GMT=true
  - GMT_DIR=/app/gmt
volumes:
  - ./gmt:/app/gmt
```

## 步骤 3：重启服务

```bash
# 如果使用 Docker Compose
docker-compose restart

# 如果直接运行
python main.py
```

## 验证

服务启动后，检查日志确认是否使用本地文件：

```bash
# 查看日志
tail -f log

# 应该看到类似这样的日志：
# INFO - 尝试使用本地 GMT 文件进行富集分析
# INFO - 使用本地文件进行富集分析: GO_Biological_Process_2021
# INFO - 成功使用本地文件完成富集分析
```

## 常见问题

### Q: 如何知道需要下载哪些库？

A: 查看 `service_config.json` 中的 `parameter_template`，默认使用的是 `GO_Biological_Process_2021`。

### Q: 下载失败怎么办？

A: 
1. 检查网络连接
2. 尝试单独下载某个库：`python download_enrichr_libraries.py --libraries GO_Biological_Process_2021`
3. 如果网络不稳定，可以多次运行脚本，已下载的文件会被跳过（需要手动删除已下载的文件才能重新下载）

### Q: 如何更新库文件？

A: 删除旧的 `.gmt` 文件，然后重新运行下载脚本。

### Q: 文件太大怎么办？

A: 只下载需要的库，不要使用 `--all` 选项。

## 下一步

- 查看 [OFFLINE_MODE.md](./OFFLINE_MODE.md) 了解详细配置
- 查看 [README.md](./README.md) 了解服务使用说明

