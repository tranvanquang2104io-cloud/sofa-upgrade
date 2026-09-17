/*
 * Shared document-form utilities.
 *
 * These three functions were copy-pasted into the document templates:
 * fmtNum into 7 of them, numberToWordsVi into 4, parseRawFee into 4. Every
 * copy was verified byte-identical before extraction (parseRawFee's two
 * apparent variants differed only in a parameter name), so moving them here
 * changes no behaviour - it just means a fix lands once instead of seven
 * times, and the Vietnamese number-to-words rules (mốt / lăm / mươi) live in
 * exactly one place.
 *
 * recalcAll() is deliberately NOT here: its body genuinely differs per
 * document type (handover prices by accepted quantity, payment has a
 * no-line-items branch), so a single shared version would have to fake those
 * differences. Those stay with their templates until they are unified on
 * purpose rather than by accident.
 *
 * Loaded globally from base.html, so every template sees these as globals
 * exactly as it did when they were inline.
 */

function fmtNum(n) {
    return new Intl.NumberFormat('vi-VN').format(Math.round(n));
}

function parseRawFee(displayId) {
    const el = document.getElementById(displayId);
    return parseInt((el ? el.value : '0').replace(/\D/g, '')) || 0;
}

function numberToWordsVi(n) {
    n = Math.round(n);
    if (!n || n === 0) return 'Không đồng';
    const u = ['', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín'];
    function r3(x, notFirst) {
        if (x === 0) return '';
        let s = '', h = Math.floor(x/100), rem = x%100, t = Math.floor(rem/10), d = rem%10;
        if (h) { s += u[h] + ' trăm'; if (rem) s += ' '; }
        else if (notFirst && rem) s += 'không trăm ';
        if (rem >= 10 && rem <= 19) { s += ['mười','mười một','mười hai','mười ba','mười bốn','mười lăm','mười sáu','mười bảy','mười tám','mười chín'][rem-10]; }
        else if (t > 1) { s += u[t]+' mươi'; if (d===1) s+=' mốt'; else if (d===5) s+=' lăm'; else if (d) s+=' '+u[d]; }
        else if (t === 1) { s += ['mười','mười một','mười hai','mười ba','mười bốn','mười lăm','mười sáu','mười bảy','mười tám','mười chín'][d]; }
        else if (d) { s += (h || notFirst) ? 'lẻ '+u[d] : u[d]; }
        return s.trim();
    }
    const ty=Math.floor(n/1e9), tr=Math.floor((n%1e9)/1e6), ng=Math.floor((n%1e6)/1e3), con=n%1e3;
    let parts=[];
    if(ty)  parts.push(r3(ty,false)+' tỷ');
    if(tr)  parts.push(r3(tr, ty>0)+' triệu');
    if(ng)  parts.push(r3(ng, tr>0||ty>0)+' nghìn');
    if(con) parts.push(r3(con, ng>0||tr>0||ty>0));
    const res = parts.join(' ').trim();
    return res.charAt(0).toUpperCase()+res.slice(1)+' đồng';
}
