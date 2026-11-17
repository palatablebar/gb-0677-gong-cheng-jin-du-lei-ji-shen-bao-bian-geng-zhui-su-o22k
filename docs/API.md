# 接口

模块GET使用仓内样例，模块POST可传csv或rows与context，直接计算当前规则。/api/runs使用完整流水线并原子保存。每个阶段返回rows、quarantine、metrics；后续阶段还返回累计隔离。/api/upload接收multipart文件file。/api/runs/<id>/archive只导出一份带清单与证据的CSV。

扣回核算接受parameters：retention_rate、advance_rate、advance_total、advance_recovered。给出advance_total时，metrics含advance_cap（本期扣回上限）、advance_deducted、advance_remaining（剩余预付款）、capped_rows，每行带advance_basis。POST /api/runs/<id>/activate把该批签证切换为项目当前签证，可带project；GET /api/certificates/active返回当前签证状态。
