from fastapi import APIRouter, Depends
from dependencies import User, get_current_active_user

router = APIRouter(
    prefix='/user',
    tags=['user'],
    dependencies=[Depends(get_current_active_user)],
    responses={403: {'description': 'Forbidden'}},
)


@router.get('/me', response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
