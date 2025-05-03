import re
from app.util.banned_words import banned_words, banned_words_regex, unicode_substitutions

class TextNotAllowed( Exception ):
    pass

unicode_lookup = {char: normalized for normalized, chars in unicode_substitutions.items() for char in chars}
def normalize_text(text):
    return ''.join(unicode_lookup.get(char, char) for char in text)

def filter_text(
    text_to_filter : str,
    raise_exception : bool = False,
    replacement_char : str = "#"
) -> str:
    banned_words.sort( key = len, reverse = True )
    banned_words_regex.sort( key = len, reverse = True )
    normal_text = normalize_text(text_to_filter.lower())
    
    for banned_word in banned_words:
        if banned_word in normal_text:
            if raise_exception:
                raise TextNotAllowed( f"Text contains banned word: {banned_word}" )
            text_to_filter = text_to_filter.replace( banned_word, replacement_char * len(banned_word) )
    
    for banned_word_regex in banned_words_regex:
        search_results = re.findall( banned_word_regex, normal_text )
        for search_result in search_results:
            if raise_exception:
                raise TextNotAllowed( f"Text contains banned word: {search_result}" )
            text_to_filter = text_to_filter.replace( search_result, replacement_char * len(search_result) )
    
    return text_to_filter