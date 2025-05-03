"""
    locale.roblox.com
"""

from quart import Blueprint, request, jsonify, make_response

LocaleRoute = Blueprint('locale_roblox', __name__, url_prefix='/', subdomain='locale')

@LocaleRoute.route("/v1/locales/user-localization-locus-supported-locales", methods=["GET"])
async def _get_user_localization_locus_supported_locales():
    return jsonify({"signupAndLogin":{"id":1,"locale":"en_us","name":"English(US)","nativeName":"English","language":{"id":41,"name":"English","nativeName":"English","languageCode":"en","isRightToLeft":False}},"generalExperience":{"id":1,"locale":"en_us","name":"English(US)","nativeName":"English","language":{"id":41,"name":"English","nativeName":"English","languageCode":"en","isRightToLeft":False}},"ugc":{"id":1,"locale":"en_us","name":"English(US)","nativeName":"English","language":{"id":41,"name":"English","nativeName":"English","languageCode":"en","isRightToLeft":False}}})