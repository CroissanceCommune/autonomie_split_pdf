import os, errno


def mkdir_p(path, logger):
    """
    http://stackoverflow.com/questions/600268/mkdir-p-functionality-in-python
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            self.critical("Error while creating directory %s -see trace" % path)
            raise
