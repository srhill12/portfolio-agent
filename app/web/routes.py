from __future__ import annotations

import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import session as auth_session
from app.calculations import LotInput, combine_positions, lot_metrics, round_money
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.models.enums import AccountType
from app.services import accounts as accounts_service
from app.services import holdings as holdings_service
from app.services import users as users_service
from app.services.errors import NotFoundError, ValidationError
from app.web.deps import (
    get_current_web_user,
    get_optional_web_user,
    require_csrf,
)

router = APIRouter(tags=["web"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def _csrf_for_request(request: Request) -> tuple[str, bool]:
    settings = get_settings()
    token = request.cookies.get(settings.csrf_cookie_name)
    if token:
        return token, False
    return secrets.token_urlsafe(32), True


def _attach_csrf(response: HTMLResponse, token: str, set_cookie: bool) -> HTMLResponse:
    if set_cookie:
        settings = get_settings()
        response.set_cookie(
            key=settings.csrf_cookie_name,
            value=token,
            max_age=60 * 60 * 24 * 14,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
            path="/",
        )
    return response


@router.get("/", response_class=HTMLResponse, response_model=None)
def home(
    request: Request,
    user: User | None = Depends(get_optional_web_user),
) -> HTMLResponse | RedirectResponse:
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "landing.html", {"user": None})


@router.get("/dashboard", response_class=HTMLResponse, response_model=None)
def dashboard(
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    csrf_token, set_csrf = _csrf_for_request(request)
    accounts = accounts_service.list_accounts(db, user.id)
    lots = holdings_service.list_lots(db, user.id)

    lots_by_account: dict[uuid.UUID, list] = {a.id: [] for a in accounts}
    for lot in lots:
        lots_by_account.setdefault(lot.account_id, []).append(lot)

    account_sections = []
    for account in accounts:
        rows = []
        for lot in lots_by_account.get(account.id, []):
            metrics = lot_metrics(
                LotInput(lot.ticker, lot.account_id, lot.quantity, lot.unit_cost),
                None,
            )
            rows.append(
                {
                    "lot": lot,
                    "cost_basis": round_money(metrics.cost_basis),
                }
            )
        account_sections.append({"account": account, "lots": rows})

    lot_inputs = [
        LotInput(lot.ticker, lot.account_id, lot.quantity, lot.unit_cost)
        for lot in lots
    ]
    combined = [
        {
            "ticker": position.ticker,
            "total_quantity": position.total_quantity,
            "average_cost": round_money(position.average_cost),
            "total_cost": round_money(position.total_cost),
        }
        for position in combine_positions(lot_inputs, {})
    ]

    response = templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "csrf_token": csrf_token,
            "accounts": accounts,
            "account_sections": account_sections,
            "combined": combined,
        },
    )
    return _attach_csrf(response, csrf_token, set_csrf)


@router.get("/login")
def login() -> RedirectResponse:
    settings = get_settings()
    state_value = secrets.token_urlsafe(32)
    authorization_url = auth_session.build_authorization_url(state_value, settings)
    response = RedirectResponse(url=authorization_url, status_code=303)
    response.set_cookie(
        key=settings.oauth_state_cookie_name,
        value=state_value,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return response


@router.get("/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    expected = request.cookies.get(settings.oauth_state_cookie_name)
    if not code or not state or not expected or state != expected:
        response = RedirectResponse(url="/?error=oauth_state", status_code=303)
        auth_session.clear_oauth_state_cookie(response, settings)
        return response

    try:
        sealed, user_dict = auth_session.exchange_code_for_sealed_session(code, settings)
    except Exception:
        response = RedirectResponse(url="/?error=auth_failed", status_code=303)
        auth_session.clear_oauth_state_cookie(response, settings)
        return response

    auth_subject = str(user_dict.get("id") or "")
    if not auth_subject:
        response = RedirectResponse(url="/?error=auth_failed", status_code=303)
        auth_session.clear_oauth_state_cookie(response, settings)
        return response

    name = user_dict.get("name")
    if not name:
        first = user_dict.get("first_name") or ""
        last = user_dict.get("last_name") or ""
        name = f"{first} {last}".strip() or user_dict.get("email")

    users_service.upsert_user_from_workos(
        db,
        auth_subject=auth_subject,
        email=user_dict.get("email"),
        name=name,
        github_login=None,
    )

    response = RedirectResponse(url="/dashboard", status_code=303)
    auth_session.set_session_cookie(response, sealed, settings)
    auth_session.set_csrf_cookie(response, settings)
    auth_session.clear_oauth_state_cookie(response, settings)
    return response


@router.post("/logout")
def logout(
    request: Request,
    _csrf: str = Depends(require_csrf),
) -> RedirectResponse:
    settings = get_settings()
    logout_url = auth_session.get_logout_url(request, settings)
    response = RedirectResponse(url=logout_url or "/", status_code=303)
    auth_session.clear_session_cookie(response, settings)
    auth_session.clear_csrf_cookie(response, settings)
    return response


@router.get("/accounts/new", response_class=HTMLResponse, response_model=None)
def new_account_form(
    request: Request,
    user: User = Depends(get_current_web_user),
) -> HTMLResponse:
    csrf_token, set_csrf = _csrf_for_request(request)
    response = templates.TemplateResponse(
        request,
        "account_form.html",
        {
            "user": user,
            "csrf_token": csrf_token,
            "form": {"name": "", "type": AccountType.investment.value},
            "errors": {},
        },
    )
    return _attach_csrf(response, csrf_token, set_csrf)


@router.post("/accounts", response_class=HTMLResponse, response_model=None)
def create_account(
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
    _csrf: str = Depends(require_csrf),
    name: str = Form(""),
    type: str = Form("investment"),
) -> HTMLResponse | RedirectResponse:
    try:
        accounts_service.create_account(db, user.id, name=name, account_type=type)
    except ValidationError as exc:
        csrf_token, set_csrf = _csrf_for_request(request)
        errors = {exc.field or "name": exc.message}
        response = templates.TemplateResponse(
            request,
            "account_form.html",
            {
                "user": user,
                "csrf_token": csrf_token,
                "form": {"name": name, "type": type},
                "errors": errors,
            },
            status_code=400,
        )
        return _attach_csrf(response, csrf_token, set_csrf)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/accounts/{account_id}/edit", response_class=HTMLResponse, response_model=None)
def edit_account_form(
    account_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    account = accounts_service.get_account(db, user.id, account_id)
    if account is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    csrf_token, set_csrf = _csrf_for_request(request)
    response = templates.TemplateResponse(
        request,
        "account_form.html",
        {
            "user": user,
            "csrf_token": csrf_token,
            "account": account,
            "form": {"name": account.name, "type": account.type.value},
            "errors": {},
        },
    )
    return _attach_csrf(response, csrf_token, set_csrf)


@router.post(
    "/accounts/{account_id}",
    response_class=HTMLResponse,
    response_model=None,
)
def update_account(
    account_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
    _csrf: str = Depends(require_csrf),
    name: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    try:
        accounts_service.rename_account(db, user.id, account_id, name=name)
    except NotFoundError:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    except ValidationError as exc:
        account = accounts_service.get_account(db, user.id, account_id)
        csrf_token, set_csrf = _csrf_for_request(request)
        response = templates.TemplateResponse(
            request,
            "account_form.html",
            {
                "user": user,
                "csrf_token": csrf_token,
                "account": account,
                "form": {
                    "name": name,
                    "type": account.type.value if account else "investment",
                },
                "errors": {exc.field or "name": exc.message},
            },
            status_code=400,
        )
        return _attach_csrf(response, csrf_token, set_csrf)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/holdings/new", response_class=HTMLResponse, response_model=None)
def new_holding_form(
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    accounts = accounts_service.list_accounts(db, user.id)
    if not accounts:
        return RedirectResponse(url="/accounts/new", status_code=303)
    csrf_token, set_csrf = _csrf_for_request(request)
    response = templates.TemplateResponse(
        request,
        "holding_form.html",
        {
            "user": user,
            "csrf_token": csrf_token,
            "accounts": accounts,
            "idempotency_key": str(uuid.uuid4()),
            "form": {
                "account_id": str(accounts[0].id),
                "ticker": "",
                "quantity": "",
                "unit_cost": "",
                "purchase_date": "",
            },
            "errors": {},
        },
    )
    return _attach_csrf(response, csrf_token, set_csrf)


@router.post("/holdings", response_class=HTMLResponse, response_model=None)
def create_holding(
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
    _csrf: str = Depends(require_csrf),
    account_id: str = Form(""),
    ticker: str = Form(""),
    quantity: str = Form(""),
    unit_cost: str = Form(""),
    purchase_date: str = Form(""),
    idempotency_key: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    accounts = accounts_service.list_accounts(db, user.id)
    form = {
        "account_id": account_id,
        "ticker": ticker,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "purchase_date": purchase_date,
    }
    try:
        parsed_account_id = uuid.UUID(account_id)
    except ValueError:
        csrf_token, set_csrf = _csrf_for_request(request)
        response = templates.TemplateResponse(
            request,
            "holding_form.html",
            {
                "user": user,
                "csrf_token": csrf_token,
                "accounts": accounts,
                "idempotency_key": idempotency_key or str(uuid.uuid4()),
                "form": form,
                "errors": {"account_id": "Choose one of your accounts."},
            },
            status_code=400,
        )
        return _attach_csrf(response, csrf_token, set_csrf)

    try:
        holdings_service.add_lot(
            db,
            user.id,
            account_id=parsed_account_id,
            ticker=ticker,
            quantity=quantity,
            unit_cost=unit_cost,
            purchase_date=purchase_date or None,
            idempotency_key=idempotency_key or None,
        )
    except NotFoundError:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    except ValidationError as exc:
        csrf_token, set_csrf = _csrf_for_request(request)
        response = templates.TemplateResponse(
            request,
            "holding_form.html",
            {
                "user": user,
                "csrf_token": csrf_token,
                "accounts": accounts,
                "idempotency_key": idempotency_key or str(uuid.uuid4()),
                "form": form,
                "errors": {exc.field or "ticker": exc.message},
            },
            status_code=400,
        )
        return _attach_csrf(response, csrf_token, set_csrf)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get(
    "/holdings/{lot_id}/edit",
    response_class=HTMLResponse,
    response_model=None,
)
def edit_holding_form(
    lot_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lot = holdings_service.get_lot(db, user.id, lot_id)
    if lot is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    accounts = accounts_service.list_accounts(db, user.id)
    csrf_token, set_csrf = _csrf_for_request(request)
    response = templates.TemplateResponse(
        request,
        "holding_form.html",
        {
            "user": user,
            "csrf_token": csrf_token,
            "accounts": accounts,
            "lot": lot,
            "form": {
                "account_id": str(lot.account_id),
                "ticker": lot.ticker,
                "quantity": str(lot.quantity),
                "unit_cost": str(lot.unit_cost),
                "purchase_date": lot.purchase_date.isoformat() if lot.purchase_date else "",
            },
            "errors": {},
        },
    )
    return _attach_csrf(response, csrf_token, set_csrf)


@router.post(
    "/holdings/{lot_id}",
    response_class=HTMLResponse,
    response_model=None,
)
def update_holding(
    lot_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
    _csrf: str = Depends(require_csrf),
    account_id: str = Form(""),
    ticker: str = Form(""),
    quantity: str = Form(""),
    unit_cost: str = Form(""),
    purchase_date: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    accounts = accounts_service.list_accounts(db, user.id)
    form = {
        "account_id": account_id,
        "ticker": ticker,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "purchase_date": purchase_date,
    }
    try:
        parsed_account_id = uuid.UUID(account_id)
    except ValueError:
        lot = holdings_service.get_lot(db, user.id, lot_id)
        if lot is None:
            return templates.TemplateResponse(
                request, "not_found.html", {"user": user}, status_code=404
            )
        csrf_token, set_csrf = _csrf_for_request(request)
        response = templates.TemplateResponse(
            request,
            "holding_form.html",
            {
                "user": user,
                "csrf_token": csrf_token,
                "accounts": accounts,
                "lot": lot,
                "form": form,
                "errors": {"account_id": "Choose one of your accounts."},
            },
            status_code=400,
        )
        return _attach_csrf(response, csrf_token, set_csrf)

    try:
        holdings_service.update_lot(
            db,
            user.id,
            lot_id,
            account_id=parsed_account_id,
            ticker=ticker,
            quantity=quantity,
            unit_cost=unit_cost,
            purchase_date=purchase_date or None,
        )
    except NotFoundError:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    except ValidationError as exc:
        lot = holdings_service.get_lot(db, user.id, lot_id)
        csrf_token, set_csrf = _csrf_for_request(request)
        response = templates.TemplateResponse(
            request,
            "holding_form.html",
            {
                "user": user,
                "csrf_token": csrf_token,
                "accounts": accounts,
                "lot": lot,
                "form": form,
                "errors": {exc.field or "ticker": exc.message},
            },
            status_code=400,
        )
        return _attach_csrf(response, csrf_token, set_csrf)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get(
    "/holdings/{lot_id}/delete",
    response_class=HTMLResponse,
    response_model=None,
)
def delete_holding_confirm(
    lot_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lot = holdings_service.get_lot(db, user.id, lot_id)
    if lot is None:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    csrf_token, set_csrf = _csrf_for_request(request)
    response = templates.TemplateResponse(
        request,
        "holding_delete.html",
        {"user": user, "csrf_token": csrf_token, "lot": lot},
    )
    return _attach_csrf(response, csrf_token, set_csrf)


@router.post(
    "/holdings/{lot_id}/delete",
    response_class=HTMLResponse,
    response_model=None,
)
def delete_holding(
    lot_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_web_user),
    db: Session = Depends(get_db),
    _csrf: str = Depends(require_csrf),
) -> HTMLResponse | RedirectResponse:
    try:
        holdings_service.delete_lot(db, user.id, lot_id)
    except NotFoundError:
        return templates.TemplateResponse(
            request, "not_found.html", {"user": user}, status_code=404
        )
    return RedirectResponse(url="/dashboard", status_code=303)
