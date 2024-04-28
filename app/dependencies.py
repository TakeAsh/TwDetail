from os.path import dirname, abspath, join
import json
import bcrypt
from functools import lru_cache
from typing import Self
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# https://github.com/trevorhobenshield/twitter-api-client
from twitter.scraper import Scraper, LOG_CONFIG

conf_path = join(dirname(abspath(__file__)), '../conf')


# https://stackoverflow.com/a/28174796
def jsonDumper(obj):
    try:
        return obj.toJSON()
    except:
        return obj.__dict__


class Settings(BaseSettings):
    secret_key: str
    algorithm: str = 'HS256'
    access_token_expire_minutes: int = 30
    salt: str
    tw_email: str
    tw_username: str
    tw_password: str
    tw_cookie: str
    model_config = SettingsConfigDict(
        env_file=join(conf_path, '.env'), env_file_encoding='utf-8'
    )

    def __init__(self) -> None:
        super().__init__(self)
        # print(json.dumps(self, default=jsonDumper, indent=2))


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expire: int


class User(BaseModel):
    username: str
    groups: list[str] = []
    disabled: bool = False
    _token: Token | None = None


class UserInDB(User):
    password: str


class Users(dict):
    def __init__(self) -> None:
        super().__init__(self)
        self._path = join(conf_path, 'users.json')
        self.load()

    def load(self) -> Self:
        with open(self._path) as f:
            self.update({u.username: u for u in [UserInDB(**u) for u in json.load(f)]})
        # print(json.dumps(self, default=jsonDumper, indent=2))
        return self

    def to_list(self) -> list[UserInDB]:
        return [
            self[username]
            for username in sorted(
                [username for username in self if username[0] != '_']
            )
        ]

    def save(self) -> None:
        with open(self._path, 'wt') as f:
            f.write(json.dumps(self.to_list(), default=jsonDumper, indent=2))

    def add(self, **kwargs) -> None:
        kwargs['password'] = get_password_hash(kwargs['password'])
        new_user = UserInDB(**kwargs)
        self[new_user.username] = new_user


@lru_cache
def get_settings():
    return Settings()


@lru_cache
def get_scraper():
    settings = get_settings()
    log_config = {}
    log_config.update(LOG_CONFIG)
    log_config['handlers']['file']['filename'] = join(
        dirname(abspath(__file__)), '../log/twitter.log'
    )
    # scraper = Scraper(settings.tw_email, settings.tw_username, settings.tw_password)
    scraper = Scraper(
        cookies=join(conf_path, settings.tw_cookie + '.cookies'),
        log_config=log_config,
        save=False,
        debug=1,
        pbar=False,
    )
    scraper.save_cookies(join(conf_path, settings.tw_cookie))
    return scraper


users = Users()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='token')


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def get_password_hash(password: str):
    settings = get_settings()
    return bcrypt.hashpw(password.encode(), settings.salt.encode())


def authenticate_user(user_db, username: str, password: str):
    user = user_db.get(username)
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> Token:
    settings = get_settings()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return Token(
        access_token=encoded_jwt,
        expire=int(expire.timestamp() * 1000),
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
):
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        # print(f"payload: {payload}")
        username: str = payload.get('sub')
        if username is None:
            raise credentials_exception
    except JWTError as e:
        print(f"[Error] get_current_user: {e}")
        raise credentials_exception
    user = users.get(username)
    if user is None:
        raise credentials_exception
    user._token = Token(access_token=token, expire=payload['exp'] * 1000)
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail='Inactive user')
    return current_user


async def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    if not any(group == 'admin' for group in current_user.groups):
        raise HTTPException(status_code=403, detail='Forbidden')
    return current_user
