
true_statement = ('y', 'yes', 'on', '1', 'true', 't', )


def booleanize(value: str) -> bool:
    """
    This function will try to assume that provided string value is boolean in some way. It will accept a wide range
    of values for strings like ('y', 'yes', 'on', '1', 'true' and 't'. Any other value will be treated as false
    :param value: any value
    :return: boolean statement
    """
    return value.lower() in true_statement
