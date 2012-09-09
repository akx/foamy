def self_or_child(element, tag):
    if element.tag == tag:
        return element
    else:
        return element.find(tag)
