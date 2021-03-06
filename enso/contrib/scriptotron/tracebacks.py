import sys
import traceback
from xml.sax.saxutils import escape as xml_escape

import enso.selection
from enso.messages import displayMessage
from enso.commands import CommandObject

MAX_EXCEPTION_TEXT_LENGTH = 80

def _makeExcInfoMsgText( exceptionType, exception, tb ):
    fileName, lineNo, funcName, _ = traceback.extract_tb( tb )[-1]
    exceptionText = unicode( exception )
    if len( exceptionText ) > MAX_EXCEPTION_TEXT_LENGTH:
        exceptionText = exceptionText[:MAX_EXCEPTION_TEXT_LENGTH] + "..."
    mainText = "A python %s exception occurred with the text '%s' in the " \
              "file '%s', line %s, function '%s'." % (
        exception.__class__.__name__,
        exceptionText,
        fileName,
        lineNo,
        funcName
        )
    mainText = xml_escape( mainText )
    msgText = "<p>%s</p>" \
              "<caption>Run the 'traceback' command for more " \
              "details.</caption>" % mainText
    return msgText


class TracebackCommand( CommandObject ):
    NAME = "traceback"
    DESCRIPTION = "Returns the latest traceback from a command."

    tracebackText = "No last traceback."

    def __init__( self ):
        CommandObject.__init__( self )
        self.setName( self.NAME )
        self.setDescription( self.DESCRIPTION )

    def run( self ):
        enso.selection.set( {"text" : self.tracebackText} )

    @classmethod
    def setTracebackInfo( cls ):
        tbText = "Scriptotron exception:\n%s" % \
            traceback.format_exc()
        cls.tracebackText = tbText
        displayMessage( _makeExcInfoMsgText(*sys.exc_info()) )


def safetyNetted( func ):
    """
    Decorator that wraps the given function in a try..except clause;
    if any exception is raised by the function, a transparent message
    is displayed informing the user, and they will be able to use the
    'traceback' command to investigate further.

    If an exception occurs, the wrapped function will return None.
    """

    def wrapper( *args, **kwargs ):
        try:
            return func( *args, **kwargs )
        except Exception, e:
            TracebackCommand.setTracebackInfo()
            print traceback.format_exc()
            return None
    return wrapper
