from app.models.user import User
from app.models.user_asset import UserAsset
from app.models.asset import Asset

from app.enums.QueryDirection import QueryDirection

class EconomyResaleExceptions:
    class AssetIsNotLimited( Exception ):
        pass

async def QueryAssetResaleListings(
    TargetAssetObj : Asset,
    OrderDirection : QueryDirection,
    Limit : int,
    Page : int = 1
) -> list[ UserAsset ]:
    """
        Query the listings for a given asset

        :param TargetAssetObj: The asset to query the listings for
        :param OrderDirection: The direction to order the listings in by price
        :param Limit: The maximum number of listings to return
        :param Page: The page of listings to return

        :return: The listings for the asset
    """

    if not TargetAssetObj.is_limited:
        raise EconomyResaleExceptions.AssetIsNotLimited( f"Asset {TargetAssetObj.id} is not limited" )
    if Limit < 1:
        raise ValueError( f"Invalid limit {Limit}" )
    if Page < 1:
        raise ValueError( f"Invalid page {Page}" )
    
    QueryObj = UserAsset.query.filter_by( asset_id = TargetAssetObj.id, is_for_sale = True )
    if OrderDirection == QueryDirection.Ascending:
        QueryObj = QueryObj.order_by( UserAsset.robux_price.asc() )
    else:
        QueryObj = QueryObj.order_by( UserAsset.robux_price.desc() )
    
    return QueryObj.paginate(
        page = Page,
        per_page = Limit
    ).items
    
