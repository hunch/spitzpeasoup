import re

from BeautifulSoup import BeautifulSoup

class SpitzpeaSoup(object):
    """ SpitzpeaSoup is a wrapper for BeautifulSoup that limits the amount
    of DOM parsing the BeautifulSoup has to do.  For certain situations
    where we don't need to traverse the entire DOM or analyze parent-child
    relationships, this may be preferable.  SpitzpeaSoup implements
    findAll() by using regular expressions to find interesting elements,
    passing only the relevant sections of code to BeautifulSoup for the
    actual DOM parse. """

    opentag_regex_cache = {}
    closetag_regex_cache = {}

    html_comment_regex = re.compile(r'<!--.*?-->', re.DOTALL)
    html_script_regex = re.compile(r'<script.*?</script\s*>', re.IGNORECASE | re.DOTALL)
    html_detector_regex = re.compile(r'<html|/html>', re.IGNORECASE | re.DOTALL)
    def __init__(self, html):
        commentless = ""

        # strip out the comments
        start = 0
        for match in self.html_comment_regex.finditer(html):
            commentless += html[start:match.start()]
            start = match.end()
        commentless += html[start:]

        # strip out the script tags (which can generate html)
        scriptless = ""
        start = 0
        for match in self.html_script_regex.finditer(commentless):
            scriptless += commentless[start:match.start()]
            start = match.end()
        scriptless += commentless[start:]

        self.html = scriptless

        # if we don't have anything that looks like html, None it out
        if not self.html_detector_regex.search(self.html):
            self.html = None

    def __getattribute__(self, name):
        if name == "title":
            # special case of find()
            return self.find("title")
        return object.__getattribute__(self, name)

    attr_regex = re.compile(r'\s*(\w+)\s*=\s*(".*?"|\'.*?\'|\S*)', re.DOTALL)
    def findAll(self, name, attrs=None, limit=None, **kwargs):
        if not self.html:
            return []

        required_attrs = attrs or {}
        if kwargs:
            required_attrs = required_attrs.copy()
            required_attrs.update(kwargs)

        def get_opentag_regex(name):
            if name not in self.opentag_regex_cache:
                self.opentag_regex_cache[name] = re.compile(r'<(?P<tagname>%s)\s*(?P<attrs>(?:\s*\w+\s*=\s*(?:".*?"|\'.*?\'|\S+?))*)\s*(?P<no_endtag>/?)>' % name, re.IGNORECASE | re.DOTALL)
            return self.opentag_regex_cache[name]

        def get_closetag_regex(name):
            if name not in self.closetag_regex_cache:
                self.closetag_regex_cache[name] = re.compile(r'</\s*%s\s*>' % name, re.IGNORECASE | re.DOTALL)
            return self.closetag_regex_cache[name]

        def attrs_match(attr_dct):
            for required_key, required_value in required_attrs.iteritems():
                if required_key not in attr_dct:
                    return False

                # if it's a regex, make sure the value matches
                if hasattr(required_value, "match"):
                    if not required_value.search(attr_dct[required_key]):
                        return False
                elif required_value != attr_dct[required_key]:
                    # make sure the string representations are equal
                    return False

            return True

        #             starts with tag, any number of attributes, perhaps trailing slash, optional inner_content + ending tag
        opentag_regex = get_opentag_regex(name)
        all_matches = []
        try:
            for opentag_match in opentag_regex.finditer(self.html):
                attr_dct = {}
                for attr_key, attr_value in self.attr_regex.findall(opentag_match.group("attrs")):
                    for quot in ["'", '"']:
                        if attr_value.startswith(quot) and attr_value.endswith(quot):
                            attr_value = attr_value[1:-1]
                            break
                    attr_dct[attr_key] = attr_value

                if not attrs_match(attr_dct):
                    continue

                tag_html = opentag_match.group(0)
                if not opentag_match.group("no_endtag"):
                    opentag_endpos = opentag_match.end()
                    cur_startpos = opentag_endpos

                    closetag_regex = get_closetag_regex(name)
                    for closetag_match in closetag_regex.finditer(self.html[opentag_endpos:]):
                        # if there's another opentag before this endtag, then check the next endtag
                        inner_opentag_match = opentag_regex.search(self.html[cur_startpos:(opentag_endpos+closetag_match.start())])
                        if not inner_opentag_match:
                            # this is the endtag that matches our original opentag
                            tag_html = self.html[opentag_match.start():(opentag_endpos+closetag_match.end())]
                            break
                        else:
                            # keep searching, starting at the end of this new opentag
                            cur_startpos += inner_opentag_match.end()

                all_matches.append(BeautifulSoup(tag_html).contents[0])

                if limit is not None and len(all_matches) >= limit: break
        except:
            pass

        return all_matches

    def find(self, *args, **kwargs):
        all_elems = self.findAll(*args, limit=1, **kwargs)
        if all_elems:
            return all_elems[0]
        return None
