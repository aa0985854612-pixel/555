'use strict';
/* One farm ledger: received quantities are derived from original orders by date. */
(() => {
Object.assign(words,{
 feedReceiptScheduled:['預定到料','Dự kiến nhận cám'],
 feed_receipt_possible_capacity:['若選擇「另外新增」，會超過料桶安全容量；請核對應新增還是更正原筆。','Nếu thêm lần khác sẽ vượt sức chứa an toàn; kiểm tra cần thêm hay sửa bản cũ.'],
 feedReceiptHint:['叫料就是到料，只登記一次。依紀錄日期計入到料與庫存；未來日期尚未計入目前庫存。實際耗料另行登記。','Đặt cám là nhận cám, chỉ ghi một lần. Tính nhập và tồn theo ngày ghi; ngày tương lai chưa cộng tồn hiện tại. Tiêu thụ thực tế ghi riêng.'],
 feedReceiptReviewRequired:['請使用飼料登記核對儲存；叫料與到料只登記一次。','Ghi và đối chiếu trong mục cám; chỉ ghi một lần đặt/nhận.']
});
Object.assign(errorWords,{feed_receipt_use_order:words.feedReceiptReviewRequired,feed_receipt_review_required:words.feedReceiptReviewRequired});
const policyWords={
 newFeedOrder:['飼料登記','Ghi nhận cám'],orderHistory:['飼料到料紀錄','Lịch sử nhận cám'],orderAmount:['到料量','Lượng cám nhận'],orderTotal:['到料合計','Tổng cám nhận'],feed_orders:['到料量','Lượng nhận cám'],
 feedSub:['叫料就是到料，日期、料桶與數量只需登記一次。','Đặt cám là nhận cám; chỉ ghi ngày, bồn và lượng một lần.'],orderMeaning:words.feedReceiptHint,quickOrderHint:words.feedReceiptHint,quick_order:['飼料到料','Nhận cám'],
 binStockHint:['以盤點基準＋已登記到料－已登記實耗計算；叫料紀錄就是到料紀錄，不必重填。帳面庫存不等於現場實測剩料。','Tính từ kiểm kê + cám nhận − tiêu thụ đã ghi. Bản ghi đặt là bản ghi nhận, không ghi lại. Tồn sổ khác số đo thực tế.'],
 orderFcrTitle:['到料估算料肉比','Tỷ lệ cám/tăng trọng theo cám nhận'],orderFcrPeriod:['到料期間','Kỳ nhận cám'],orderFcrOrders:['期間到料','Cám nhận trong kỳ'],orderFcrRows:['核對到料日期與噸數','Đối chiếu ngày và số tấn nhận'],orderFcrUnit:['公斤到料／公斤估算增重','kg cám nhận / kg tăng trọng ước tính'],
 orderFcrLimit:['以到料量暫代耗料，尚未扣除期初／期末剩料及校正異動重量，僅供粗估。','Tạm dùng cám nhận thay tiêu thụ; chưa chỉnh tồn đầu/cuối và khối lượng biến động, chỉ ước tính.']
};
const original=Object.fromEntries(Object.keys(policyWords).map(k=>[k,words[k]]));
const base={selections,translate,statHTML};
function labels(){const values=data?.feed_orders_are_arrivals?policyWords:original;for(const [k,v] of Object.entries(values))if(v)words[k]=v;}
selections=(force=false)=>{labels();base.selections(force);base.translate();};
translate=()=>{labels();base.translate();};
statHTML=s=>{const html=base.statHTML(s);if(!data?.feed_orders_are_arrivals)return html;return html.replace(`<div>${t('orderTotal')}<strong>${fmt(s.feed_order_kg)}</strong></div>`,'');};
})();
