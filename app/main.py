#! /usr/bin/python3

import uvicorn
import os
from os.path import dirname, abspath, join
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dependencies import (
    Token,
    User,
    users,
    oauth2_scheme,
    authenticate_user,
    create_access_token,
    get_current_active_user,
)
from routers import admin, user, tweet


app_path = dirname(abspath(__file__))

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['https://twitter.com'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.include_router(admin.router)
app.include_router(user.router)
app.include_router(tweet.router)
app.mount(
    '/scripts',
    StaticFiles(directory=join(app_path, 'scripts')),
    name='scripts',
)
templates = Jinja2Templates(directory=join(app_path, 'templates'))


@app.get('/', response_model=Token)
async def root(
    current_user: User = Depends(get_current_active_user),
):
    return current_user._token


@app.post('/token', response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = authenticate_user(users, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    return create_access_token(
        data={'sub': user.username},
    )


@app.get('/scripts', response_class=HTMLResponse)
async def list_scripts(request: Request):
    files = sorted(os.listdir(join(app_path, 'scripts')))
    # print(files)
    return templates.TemplateResponse(
        'directorylist.html',
        {'request': request, 'folder': 'scripts', 'files': files},
    )


if __name__ == '__main__':
    uvicorn.run(
        'main:app', host='localhost', port=8000, log_level='debug', reload=False
    )
