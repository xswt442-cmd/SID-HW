# Q2 SCP/SSH 分布式快速排序

## 实验方法

16 个输入文件按组号轮询分配给 K 个 Worker。程序通过 SCP 上传分组文件和 Quick Sort 程序，以 SSH 在远端排序，再用 SCP 下载结果；本机将 16 个有序分组归并为 `2453721-hw1-q2-qs.txt`。Merge Sort 程序另行读取完整输入，生成 `2453721-hw1-q2-ms.txt`。

K=2 使用 Debian 13（2 核、2 GB）和 Ubuntu 24.04（2 核、4 GB）云机。K=4 使用四个 Docker Worker 并行处理分组。Docker 镜像和容器在计时前准备完成。

## 计时结果

| 阶段 | K=2（秒） | K=4（秒） |
|---|---:|---:|
| 上传最慢 Worker | 4.933 | 3.134 |
| 远端 Quick Sort 最慢 Worker | 7.328 | 4.309 |
| 下载最慢 Worker | 21.901 | 20.625 |
| 本机最终归并 | 0.820 | 0.919 |
| time-A | 36.126 | 29.557 |
| time-B | 3.797 | 3.875 |
| time-A/time-B | 9.515 | 7.628 |

time-A 包含并行上传、远端排序、下载和本机最终归并；上传、排序和下载按并行 Worker 中最慢阶段统计。time-B 为本机 Merge Sort 从读取完整输入到输出完成的耗时，比值按题目定义计算。

K=4 的 time-A 比 K=2 少 6.569 秒，Quick Sort 阶段最慢值少 3.019 秒。下载仍是两组实验中耗时最长的阶段，分别占 time-A 的约 60.6% 和 69.8%。因此，减少排序耗时后，文件下载仍限制总体加速效果。

## 输出核对

K=2、K=4 的 Quick Sort 结果均有 2097152 行，升序排列，并与对应 Merge Sort 基准逐行一致。控制台截图分别为 `screenshots/pic2-k2.png` 和 `screenshots/pic2-k4.png`。
