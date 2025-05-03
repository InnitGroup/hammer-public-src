import os
import logging
from config import Config

web_config = Config()

async def format_template(
    template_file_name : str,
    template_file_dir : str = web_config.EMAIL_TEMPLATES_DIR,
    **kwargs
) -> str:
    """
        Formats an email template with the provided arguments
        some default values are also provided during the formatting

        website_display_name: web_config.EMAIL_WEBSITE_DISPLAY_NAME
        website_display_name_capital: web_config.EMAIL_WEBSITE_DISPLAY_NAME_CAPITAL

        :param template_file_name: The name of the template file
        :param template_file_dir: The directory of the template file
        :param kwargs: The arguments to format the template with

        :return: str
    """

    template_path = os.path.join( template_file_dir, template_file_name )
    if not os.path.exists( template_path ):
        logging.error(f"util.email_formatter > format_template: Template file not found: {template_path}")
        raise FileNotFoundError( f"Template file not found: {template_path}" )

    with open( template_path, 'r' ) as template_file:
        template_contents = template_file.read()

    return template_contents.format(
        website_display_name = web_config.EMAIL_WEBSITE_DISPLAY_NAME,
        website_display_name_capital = web_config.EMAIL_WEBSITE_DISPLAY_NAME_CAPITAL,
        **kwargs
    )