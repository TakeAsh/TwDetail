from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from dependencies import (
    Settings,
    User,
    users,
    get_settings,
    get_current_admin_user,
)

router = APIRouter(
    prefix='/admin',
    tags=['admin'],
    dependencies=[Depends(get_current_admin_user)],
    responses={401: {'description': 'Unauthorized'}},
)


@router.get('/config', response_model=Settings)
async def show_config(settings: Annotated[Settings, Depends(get_settings)]):
    return settings


@router.get('/users', response_model=list[User])
async def read_users():
    return users.to_list()


@router.post('/new_user', response_model=User)
async def new_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    users.add(
        username=form_data.username,
        password=form_data.password,
        groups=form_data.scopes,
    )
    users.save()
    return users.get(form_data.username)
