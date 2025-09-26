# 建立免費的GCP

https://kucw.io/blog/gcp-free-tier/
參考古古的方式

懶人包
機器設定：區域只能選擇「us-west1、us-central1、us-east1」其中一個
        「機型」調整為 e2-micro

OS和儲存空間：「標準永久磁碟」，上限30G

網路：勾選「允許 HTTP 流量」和「允許 HTTPS 流量」，「網路服務級別」的地方改成勾選「標準級（us-west1）」

資料保護：無備份

觀測能力：取消勾選「Ops Agent」

右邊費用為 6.91 美元
下面項目有「2vCPU + 1GB memory」和「20GB 標準永久硬碟」這兩行，如果有其他多出來的設定都是錯誤的