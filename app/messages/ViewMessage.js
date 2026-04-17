'use client';

/** @module messages/ViewMessage */

import * as React from 'react';
import ArrowBackIosOutlinedIcon from '@mui/icons-material/ArrowBackIosOutlined';
import ArrowForwardIosOutlinedIcon from '@mui/icons-material/ArrowForwardIosOutlined';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import ReplyIcon from '@mui/icons-material/Reply';
import ReplyAllIcon from '@mui/icons-material/ReplyAll';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import { Editor } from '@tinymce/tinymce-react';

import PropTypes from 'prop-types';

import UserNames from './UserNames';
import { UserNamesListContext } from '../serverInfo';

// Different types of messages
export const MESSAGE_TYPE = {
  None: -1,
  New: 0,
  Read: 1,
  Reply: 2,
  ReplyAll: 3
};

// Message navigation values
const MESSAGE_NAV = {
  prev: -1,
  next: 1,
};

/**
 * Provides the UI for a user messages. If curMessage is set, messages are read-only. Otherwise
 * it's assumed that a message is being added
 * @function
 * @param {object} [curMessage] An array of messages to display. Control is read-only
 * @param {boolean} [messageType] The MESSAGE_TYPE the current message is
 * @param {function} [onRead] Called to indicate a message has been read
 * @param {function} [onAdd] Called to add a new message. Use when creating a new message
 * @param {function} [onReply] Called to reply to an existing message
 * @param {function} [onReplyAll] Called to reply-all to an existing message
 * @param {function} onClose Called when the user is finished
 * @returns {object} The UI for managing messages
 */
export default function ViewMessage({curMessage, messageType, onRead, onAdd, onReply, onReplyAll, onClose}) {
  const theme = useTheme();
  const userNames = React.useContext(UserNamesListContext);
  const editorRef = React.useRef(null);
  const onReadRef = React.useRef(onRead);
  const recipientRef = React.useRef(null);
  const subjectRef = React.useRef(null);
  const [activeSegmentIndex, setActiveSegmentIndex] = React.useState(-1); // Segment the user is editing in the recipients
  const [curReadMessage, setCurReadMessage] = React.useState(messageType !== MESSAGE_TYPE.New && curMessage ? curMessage[0] : null); // Current message being read
  const [curMessageIndex, setCurMessageIndex] = React.useState(messageType !== MESSAGE_TYPE.New ? 0 : -1);
  const [curRecipient, setCurRecipient] = React.useState(''); // Controlled textfield
  const [curSubject, setCurSubject] = React.useState(curMessage ? curMessage[0].subject : '');    // Controlled textfield
  const [filteredUsers, setFilteredUsers] = React.useState([]);     // The filtered list of users
  const [messageError, setMessageError] = React.useState(false);    // Error with new message
  const [popupOffset, setPopupOffset] = React.useState(0);
  const [readMessageIds, setReadMessageIds] = React.useState([]);   // IDs of read messages
  const [recipientError, setRecipientError] = React.useState(false);// Error with new recipient
  const [showUsernames, setShowUserNames] =  React.useState(false); // Popup with user names
  const [subjectError, setSubjectError] = React.useState(false);    // Error with new subject

   // Keep onRead up to date
  React.useEffect(() => {
    onReadRef.current = onRead;
  }, [onRead]);

  // Determine the correct recipient
  React.useEffect(() => {
    if (!curMessage) {
      return;
    }

    if (messageType === MESSAGE_TYPE.Reply) {
      setCurRecipient(curMessage[0].sender)
    } else if (messageType === MESSAGE_TYPE.ReplyAll) {
      const allRecipient = curMessage[0].receiver.split(',').filter((item) => item.trim().toLowerCase() !== curMessage[0].sender.trim().toLowerCase())
      setCurRecipient([curMessage[0].sender, ...allRecipient].join(', '));
    } else {
      setCurRecipient(curMessage[0].receiver);
    }
  }, [curMessage, messageType, setCurRecipient]);

  // Set the first message as read
  React.useEffect(() => {
    if (curMessage && readMessageIds.length === 0) {
      setReadMessageIds([curMessage[0].id]);
      onReadRef.current([curMessage[0].id]);
    }
  }, [curMessage, readMessageIds])

  /**
   * Adds a new message
   * @function
   * @param {boolean} overrideEmptyMessage Set to true to override the message content check
   */
  const onSend = React.useCallback((overrideEmptyMessage) => {
    // Make sure we have something
    if (!editorRef.current || !recipientRef.current || !subjectRef.current) {
      return;
    }
    const recipError = !recipientRef.current.value || recipientRef.current.value.length < 2;
    const subjError = !subjectRef.current.value || subjectRef.current.value.length < 2;
    setRecipientError(recipError);
    setSubjectError(subjError);
    if (recipError || subjError) {
      return;
    }

    const message = editorRef.current.getContent();
    const msgError = (!message || message.length < 2) && !overrideEmptyMessage;
    setMessageError(msgError);

    if (msgError && !overrideEmptyMessage) {
      return;
    }

    onAdd(recipientRef.current.value, subjectRef.current.value, message, onClose);

  }, [onAdd, onClose]);

  /**
   * Handles message viewing navigation
   * @function
   * @param {number} navigation The number of messages to navigate
   */
  const handleNavigateMessage = React.useCallback((navigation) => {
    if (!(navigation in MESSAGE_NAV)) {
      return;
    }

    // Get and check the next message index
    const nextIndex = curMessageIndex + navigation;
    if (!curMessage || nextIndex < 0 || nextIndex >= curMessage.length) {
      return;
    }

    const curMsg = curMessage[nextIndex];
    setCurMessageIndex(nextIndex);
    setCurReadMessage(curMsg);
    setCurRecipient(curMsg.sender);
    setCurSubject(curMsg.subject);

    if (!readMessageIds.includes(curMsg.id)) {
      setReadMessageIds(prev => [...prev, curMsg.id]);
      onReadRef.current([curMsg.id]);
    }
  }, [curMessage, curMessageIndex, readMessageIds]);

  /**
   * Calculates the horizontal pixel offset for the username popup
   * so it appears under the segment currently being typed
   * @function
   * @param {string} value The full recipient field value
   * @param {number} activeIdx The index of the active comma-separated segment
   * @returns {number} Pixel offset from the left edge of the input
   */
  const calcPopupOffset = React.useCallback((value, activeIdx) => {
    if (!recipientRef.current || activeIdx <= 0) return 0;

    // Get the text that appears before the active segment
    const textBefore = value
      .split(',')
      .slice(0, activeIdx)
      .join(',') + ',';  // include the comma that precedes the active segment

    // Match the font the browser is actually rendering in the input
    const style = window.getComputedStyle(recipientRef.current);
    const paddingLeft = parseFloat(style.paddingLeft) || 0;

    const font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = font;

    const measuredWidth = ctx.measureText(textBefore).width;

    // Clamp so the popup never overflows past the right edge of the input
    const maxOffset = recipientRef.current.offsetWidth - 150; // 150 = min popup width
    return Math.max(0, Math.min(measuredWidth + paddingLeft, maxOffset));
  }, []);

  /**
   * Returns the active segment based upon the cursor position
   * @function
   * @param {string} value The value of the control
   * @param {number} cursorPos The cursor position
   */
  const getActiveSegment = React.useCallback((value, cursorPos) => {
    const segments = value.split(',');
    let charCount = 0;
    let activeIdx = segments.length - 1;

    for (let i = 0; i < segments.length; i++) {
      charCount += segments[i].length + 1;      // Add +1 for comma's
      if (cursorPos < charCount) {
        activeIdx = i;
        break;
      }
    }

    // Use the last space-delimited word up to the cursor as the filter text,
    // so typing within or before an existing name filters on just the current word
    const segment = segments[activeIdx];
    const segmentStart = charCount - segment.length - 1;
    const cursorWithinSegment = cursorPos - segmentStart;
    const textUpToCursor = segment.substring(0, cursorWithinSegment);
    const activeWord = textUpToCursor.split(' ').pop().trim();

    return { idx: activeIdx, segment: activeWord };
  }, []);

  /**
   * Handles when a user is selected
   * @function
   * @param {string} name The name the user selected
   */
const handleSelectUser = React.useCallback((name) => {
  const parts = curRecipient.split(',');
  const segment = parts[activeSegmentIndex];

  const segmentStart = parts
    .slice(0, activeSegmentIndex)
    .join(',')
    .length + (activeSegmentIndex > 0 ? 1 : 0);
  const cursorWithinSegment = (recipientRef.current?.selectionStart ?? segment.length) - segmentStart;

  const textUpToCursor = segment.substring(0, cursorWithinSegment);
  const textAfterCursor = segment.substring(cursorWithinSegment);

  const lastSpaceIndex = textUpToCursor.lastIndexOf(' ');
  const textBeforeWord = lastSpaceIndex >= 0
    ? textUpToCursor.substring(0, lastSpaceIndex + 1)
    : '';

  const textAfterCursorTrimmed = textAfterCursor.trimStart();

  // Appending means we are in the last segment and nothing exists after the cursor
  const isAppending = activeSegmentIndex === parts.length - 1 && 
    textAfterCursorTrimmed.length === 0;

  if (textAfterCursorTrimmed.length > 0) {
    parts.splice(activeSegmentIndex, 1,
      (activeSegmentIndex > 0 ? ' ' : '') + textBeforeWord + name,
      ' ' + textAfterCursorTrimmed
    );
  } else if (textBeforeWord.length > 0) {
    parts.splice(activeSegmentIndex, 1,
      (activeSegmentIndex > 0 ? ' ' : '') + textBeforeWord.trimEnd(),
      ' ' + name
    );
  } else {
    parts[activeSegmentIndex] = (activeSegmentIndex > 0 ? ' ' : '') + name;
  }

  const cleanedParts = parts.filter(p => p.trim().length > 0);
  const newValue = cleanedParts.join(',') + (isAppending ? ', ' : '');

  setCurRecipient(newValue);
  setShowUserNames(false);
  setFilteredUsers([]);
  setActiveSegmentIndex(-1);
  setPopupOffset(0);

  const cursorPos = isAppending
    ? newValue.length
    : cleanedParts.slice(0, activeSegmentIndex + 1).join(',').length;

  requestAnimationFrame(() => {
    if (recipientRef.current) {
      recipientRef.current.setSelectionRange(cursorPos, cursorPos);
      recipientRef.current.focus();
    }
  });

}, [curRecipient, activeSegmentIndex]);

  /**
   * Handles when the the recipents cursor position changes or value changes
   * @function
   * @param {object} target The triggering event's target value
   * @param {bool} isChange When true, indicated the event was caused by a change in the field
   */
  const handleRecipientUpdate = React.useCallback((target, isChange = false) => {
    if (isChange) setCurRecipient(target.value);

    const activeSegment = getActiveSegment(target.value, target.selectionStart);
    setActiveSegmentIndex(activeSegment.idx);

    const hasInput = activeSegment.segment.length > 0;

    // matches must be computed before isExactMatch
    const matches = hasInput
      ? userNames.names.filter(n => n.toLowerCase().startsWith(activeSegment.segment.toLowerCase()))
      : [];

    const isExactMatch = matches.length === 1 &&
      matches[0].toLowerCase() === activeSegment.segment.toLowerCase();

    setShowUserNames(hasInput && !isExactMatch);
    setFilteredUsers(matches);

    setPopupOffset(calcPopupOffset(target.value, activeSegment.idx));
    console.log('value:', target.value, 'selectionStart:', target.selectionStart, 'segment:', getActiveSegment(target.value, target.selectionStart));
  }, [calcPopupOffset, getActiveSegment, userNames]);

  /**
   * Handles when the user clicks on the receipent field
   * @function
   * @param {object} event The triggering event
   */
  const handleRecipientClick = React.useCallback((event) => {
    if (event.button === 0) {
      handleRecipientUpdate(event.target); // left-click only
    }
  }, [handleRecipientUpdate]);

  /**
   * Handles when the key up on the receipent field
   * @function
   * @param {object} event The triggering event
   */
  const handleRecipientKeyUp = React.useCallback((event) => {
    if (['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) {
      const target = event.target;
      setTimeout(() => handleRecipientUpdate(target), 0);
    }
  }, [handleRecipientUpdate]);

  // Return the UI
  return (
    <React.Fragment>
      <Grid id="new-message-wrapper" container direction="row" alignItems="center" justifyContent="center" 
            sx={{width:'100vw', height:'100vh', backgroundColor:'rgb(0,0,0,0.5)', position:'absolute', top:'0px', left:'0px', zIndex:2501}}
      >
        <Grid id="new-message-fields" container direction="column" style={{backgroundColor:'ghostwhite', border:'1px solid grey', borderRadius:'15px', padding:'25px 10px'}}>
          <div style={{ position: 'relative' }}>
            <TextField id='new-message-recipient'
                        required={messageType !== MESSAGE_TYPE.Read}
                        error={recipientError}
                        inputRef={recipientRef}
                        label={messageType === MESSAGE_TYPE.Read ? 'From' : 'To (comma separated list of names. Send to admin to notify administrators)'}
                        disabled={messageType === MESSAGE_TYPE.Read}
                        fullWidth
                        size="small"
                        variant="standard"
                        value={curRecipient}
                        onChange={(event) => handleRecipientUpdate(event.target, true)}
                        onClick={handleRecipientClick}
                        onKeyUp={handleRecipientKeyUp}
                        onBlur={() => setTimeout(() => setShowUserNames(false), 150)}
                        InputLabelProps={{
                          shrink: true, // Forces the label to move above the input
                        }}
                        sx={{marginBottom:'20px'}} />
            { showUsernames && 
              <UserNames
                filteredUsers={filteredUsers}
                popupOffset={popupOffset}
                onSelectUser={handleSelectUser}
              />
            }
          </div>
          <TextField id='new-message-subject'
                      required={messageType !== MESSAGE_TYPE.Read}
                      error={subjectError}
                      inputRef={subjectRef}
                      label='Subject'
                      disabled={messageType === MESSAGE_TYPE.Read}
                      fullWidth 
                      size="small"
                      variant="standard" 
                      value={curSubject}
                      onChange={(event) => setCurSubject(event.target.value)}
                      InputLabelProps={{
                        shrink: true, // Forces the label to move above the input
                      }}
                      sx={{marginBottom:'2em'}} />
          <Editor
            apiKey="himih4f89itmc44j6vzbjju2kavymhqdiax1u3rpvul7cj5s"
            license_key='gpl'
            onInit={(evt, editor) => editorRef.current = editor}
            initialValue={curReadMessage ? curReadMessage.message : undefined}
            disabled={messageType === MESSAGE_TYPE.Read}
            init={{
              promotion: false,
              branding: false,
              height: 200,
              menubar: false,
              elementpath: false,
              nonEditable_class: 'mceNonEditable',
              plugins: [
                'anchor', 'autolink', 'charmap', 'emoticons', 'link', 'lists',
                'searchreplace', 'table', 'wordcount',
              ],
              toolbar: 'undo redo | formatselect | ' +
              'bold italic backcolor | alignleft aligncenter ' +
              'alignright alignjustify | bullist numlist outdent indent | ' +
              'removeformat',
              content_style: 'body { font-family:Helvetica,Arial,sans-serif; font-size:14px }',
            }}
          />
          <Grid container direction="row" alignItems="center" justifyContent="space-between" sx={{paddingTop:'15px'}}>
            { messageType === MESSAGE_TYPE.Read && 
              <Grid container direction="row" alignItems="center" >
                <Button size="small" 
                        aria-label="Previous message"
                        disabled={!curMessage || curMessage.length <= 1 || curMessageIndex === 0}
                        onClick={() => handleNavigateMessage(MESSAGE_NAV.prev)}
                >
                  <ArrowBackIosOutlinedIcon fontSize="small" />
                </Button>
                <Typography variant="body2" sx={{color:curMessage.length === 1 ? 'lightgrey':'black' }}>
                  {curMessageIndex + 1} of {curMessage ? curMessage.length : "?"}
                </Typography>
                <Button size="small" 
                        aria-label="Next message"
                        disabled={!curMessage || curMessage.length <= 1 || curMessageIndex === curMessage.length-1}
                        onClick={() => handleNavigateMessage(MESSAGE_NAV.next)}
                >
                  <ArrowForwardIosOutlinedIcon fontSize="small" />
                </Button>
              </Grid>
            }
            { messageType === MESSAGE_TYPE.Read && 
              <div style={{marginLeft:'auto'}}>
                <Tooltip title='Reply'>
                  <IconButton aria-label="Reply messages" onClick={() => onReply(curReadMessage.id)} >
                    <ReplyIcon fontSize="small"/>
                  </IconButton>
                </Tooltip>
                <Tooltip title='Reply to all'>
                  <IconButton aria-label="Reply all messages" onClick={() => onReplyAll(curReadMessage.id)} >
                    <ReplyAllIcon fontSize="small"/>
                  </IconButton>
                </Tooltip>
              </div>
            }
            { messageType !== MESSAGE_TYPE.Read && <Button variant="contained" onClick={() => onSend()}>Send</Button> }
            <Button variant="contained" onClick={() => onClose()}>{messageType === MESSAGE_TYPE.Read ? "Done" : "Close"}</Button>
          </Grid>
        </Grid>
      </Grid>
      { messageError &&
        <Grid id="new-message-error-wrapper" container direction="row" alignItems="center" justifyContent="center" 
              sx={{width:'100vw', height:'100vh', backgroundColor:'rgb(0,0,0,0.5)', position:'absolute', top:'0px', left:'0px', zIndex:2502}}
        >
          <Card id="new-message-error" sx={{minWidth:'200px', backgroundColor:'ghostwhite', border:'1px solid lightgrey', borderRadius:'20px'}} >
            <CardHeader title="There is no message content" />
            <CardContent sx={{paddingTop:'0px', paddingBottom:'0px'}}>
              <Grid container direction="column" alignItems="start" justifyContent="start"
                      spacing={1}
                      sx={{paddingTop:'5px', flexWrap:'nowrap'}}
              >
              Do you still want to send the message?
              </Grid>
            </CardContent>
            <CardActions>
              <Grid container id="settings-actions-wrapper" direction="row" justifyContent='space-between' alignItems='center' sx={{width:'100%', paddingTop:'20px'}}
              >
                <Button variant="contained" onClick={() => {setMessageError(false);onSend(true);}}>Yes</Button>
                <Button variant="contained" onClick={() => setMessageError(false)}>No</Button>
              </Grid>
            </CardActions>
          </Card>
        </Grid>
      }
    </React.Fragment>
  );
}

ViewMessage.propTypes = {
  /** Array of message objects to display */
  curMessage: PropTypes.arrayOf(
    PropTypes.shape({
      id:       PropTypes.string.isRequired,
      sender:   PropTypes.string.isRequired,
      receiver: PropTypes.string.isRequired,
      subject:  PropTypes.string.isRequired,
      message:  PropTypes.string.isRequired,
    })
  ),

  /** The type of message being displayed */
  messageType: PropTypes.oneOf(Object.values(MESSAGE_TYPE)).isRequired,

  /** Called with an array of message IDs when messages are marked as read */
  onRead: PropTypes.func.isRequired,

  /** Called with (recipient, subject, message, onSuccess) to send a new message */
  onAdd: PropTypes.func.isRequired,

  /** Called with the message ID to open a reply */
  onReply: PropTypes.func.isRequired,

  /** Called with the message ID to open a reply-all */
  onReplyAll: PropTypes.func.isRequired,

  /** Called when the user closes the message dialog */
  onClose: PropTypes.func.isRequired,
};

ViewMessage.defaultProps = {
  curMessage: null,
};
