from app.extensions import redis_controller
from app.enums.WebsiteFeature import WebsiteFeature

async def GetWebsiteFeature( feature : WebsiteFeature ) -> bool:
    """
        Get the status of a website feature

        :param featureName: The feature to get the status of

        :return: The status of the feature
    """

    if not await redis_controller.exists( f"website_feature_{feature.value}" ) > 0:
        await redis_controller.set( f"website_feature_{feature.value}", "1" )
        return True
    
    return await redis_controller.get( f"website_feature_{feature.value}" ) == "1"

async def SetWebsiteFeature( feature : WebsiteFeature, status : bool ) -> None:
    """
        Set the status of a website feature

        :param featureName: The feature to set the status of
        :param status: The status to set the feature to
    """

    await redis_controller.set( f"website_feature_{feature.value}", "1" if status else "0" )