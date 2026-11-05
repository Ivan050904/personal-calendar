from fastapi import APIRouter
from app.api.routes.integration import command,command_result

router = APIRouter(tags=['calendar-commands'])
router.add_api_route('/commands',command,methods=['POST'])
router.add_api_route('/commands/{command_id}',command_result,methods=['GET'])
