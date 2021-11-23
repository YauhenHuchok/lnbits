import json
from datetime import datetime
from http import HTTPStatus

import shortuuid  # type: ignore
from fastapi import HTTPException
from fastapi.param_functions import Query
from starlette.requests import Request
from starlette.responses import HTMLResponse  # type: ignore

from lnbits.core.services import pay_invoice

from . import withdraw_ext
from .crud import get_withdraw_link_by_hash, update_withdraw_link

# FOR LNURLs WHICH ARE NOT UNIQUE


@withdraw_ext.get(
    "/api/v1/lnurl/{unique_hash}",
    response_class=HTMLResponse,
    name="withdraw.api_lnurl_response",
)
async def api_lnurl_response(request: Request, unique_hash):
    print("NOT UNIQUE")
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Withdraw link does not exist."
        )
        # return ({"status": "ERROR", "reason": "LNURL-withdraw not found."},
        #     HTTPStatus.OK,
        # )

    if link.is_spent:
        raise HTTPException(
            # WHAT STATUS_CODE TO USE??
            detail="Withdraw is spent."
        )
    url = request.url_for("withdraw.api_lnurl_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url,
        "k1": link.k1,
        "minWithdrawable": link.min_withdrawable * 1000,
        "maxWithdrawable": link.max_withdrawable * 1000,
        "defaultDescription": link.title,
    }
    return json.dumps(withdrawResponse)


# CALLBACK

#https://5650-2001-8a0-fa12-2900-4c13-748a-fbb9-a47f.ngrok.io/withdraw/api/v1/lnurl/cb/eJHybS8hqcBWajZM63H3FP?k1=MUaYBGrUPuAs8SLpfizmCk&pr=lnbc100n1pse2tsypp5ju0yn3w9j0n8rr3squg0knddawu2ude2cgrm6zje5f34e9jzpmlsdq8w3jhxaqxqyjw5qcqpjsp5tyhu78pamqg5zfy96kup329zt40ramc8gs2ev6jxgp66zca2348qrzjqwac3nxyg3f5mfa4ke9577c4u8kvkx8pqtdsusqdfww0aymk823x6znwa5qqzyqqqyqqqqlgqqqqppgq9q9qy9qsq66zp6pctnlmk59xwtqjga5lvqrkyccmafmn43enhhc6ugew80sanxymepshpv44m9yyhfgh8r2upvxhgk00d36rpqzfy3fxemeu4jhqp96l8hx


@withdraw_ext.get(
    "/api/v1/lnurl/cb/{unique_hash}",
    name="withdraw.api_lnurl_callback",
)
async def api_lnurl_callback(
    unique_hash,
    request: Request,
    k1: str = Query(...),
    pr: str = Query(...)
):
    link = await get_withdraw_link_by_hash(unique_hash)
    now = int(datetime.now().timestamp())
    if not link:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="LNURL-withdraw not found"
        )

    if link.is_spent:
        raise HTTPException(status_code=HTTPStatus.OK, detail="Withdraw is spent.")

    if link.k1 != k1:
        raise HTTPException(status_code=HTTPStatus.OK, detail="Bad request.")

    if now < link.open_time:
        return {"status": "ERROR", "reason": f"Wait {link.open_time - now} seconds."}

    try:
        usescsv = ""
        for x in range(1, link.uses - link.used):
            usecv = link.usescsv.split(",")
            usescsv += "," + str(usecv[x])
        usecsvback = usescsv
        usescsv = usescsv[1:]

        changesback = {
            "open_time": link.wait_time,
            "used": link.used,
            "usescsv": usecsvback,
        }

        changes = {
            "open_time": link.wait_time + now,
            "used": link.used + 1,
            "usescsv": usescsv,
        }
        await update_withdraw_link(link.id, **changes)
        
        payment_request=pr

        await pay_invoice(
            wallet_id=link.wallet,
            payment_request=payment_request,
            max_sat=link.max_withdrawable,
            extra={"tag": "withdraw"},
        )
        return {"status": "OK"}

    except Exception as e:
        await update_withdraw_link(link.id, **changesback)
        return {"status": "ERROR", "reason": "Link not working"}


# FOR LNURLs WHICH ARE UNIQUE


@withdraw_ext.get(
    "/api/v1/lnurl/{unique_hash}/{id_unique_hash}",
    response_class=HTMLResponse,
    name="withdraw.api_lnurl_multi_response",
)
async def api_lnurl_multi_response(request: Request, unique_hash, id_unique_hash):
    print("UNIQUE")
    link = await get_withdraw_link_by_hash(unique_hash)

    if not link:
        raise HTTPException(
            status_code=HTTPStatus.OK, detail="LNURL-withdraw not found."
        )

    if link.is_spent:
        raise HTTPException(status_code=HTTPStatus.OK, detail="Withdraw is spent.")

    useslist = link.usescsv.split(",")
    found = False
    for x in useslist:
        tohash = link.id + link.unique_hash + str(x)
        if id_unique_hash == shortuuid.uuid(name=tohash):
            found = True
    if not found:
        raise HTTPException(
            status_code=HTTPStatus.OK, detail="LNURL-withdraw not found."
        )

    url = request.url_for("withdraw.api_lnurl_callback", unique_hash=link.unique_hash)
    withdrawResponse = {
        "tag": "withdrawRequest",
        "callback": url,
        "k1": link.k1,
        "minWithdrawable": link.min_withdrawable * 1000,
        "maxWithdrawable": link.max_withdrawable * 1000,
        "defaultDescription": link.title,
    }
    return json.dumps(withdrawResponse)