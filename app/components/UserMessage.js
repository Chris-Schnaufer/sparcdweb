'use client';

/** @module components/NewUserMessage */

import * as React from 'react';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Grid from '@mui/material/Grid';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import { Editor } from '@tinymce/tinymce-react';

/**
 * Provides the UI for a user messages. If curMessage is set, messages are read-only. Otherwise
 * it's assumed that a message is being added
 * @function
 * @param {object} {curMessage} An array of messages to display
 * @param {function} {onRead} Called to indicate a message has been read
 * @param {function} {onAdd} Called to add a new message 
 * @param {function} onClose Called when the user is finished
 * @returns {object} The UI for managing messages
 */
export default function UserMessage({curMessage, onRead, onAdd, onClose}) {
  const theme = useTheme();
  const recipientRef = React.useRef(null);
  const subjectRef = React.useRef(null);
  const editorRef = React.useRef(null);
  const [curReadMessage, setCurReadMessage] = React.useState(curMessage ? curMessage[0] : null); // Current message being read
  const [curMessageIndex, setCurMessageIndex] = React.useState(curMessage ? 0 : -1);
  const [curRecipient, setCurRecipient] = React.useState(curMessage ? curMessage[0].sender : ''); // Controlled textfield
  const [curSubject, setCurSubject] = React.useState(curMessage ? curMessage[0].subject : '');    // Controlled textfield
  const [messageError, setMessageError] = React.useState(false);    // Error with new message
  const [readMessageIds, setReadMessageIds] = React.useState([]);
  const [recipientError, setRecipientError] = React.useState(false);// Error with new recipient
  const [subjectError, setSubjectError] = React.useState(false);    // Error with new subject

  const readOnly = !!curMessage;

  // Set the first message as read
  React.useEffect(() => {
    if (curMessage) {
      if (readMessageIds.length === 0) {
        setReadMessageIds([curMessage[0].id]);
        onRead([curMessage[0].id]);
      }
    }
  }, [curMessage, readMessageIds, setReadMessageIds])

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
    const recipError = !recipientRef.current.value || recipientRef.current.length < 2;
    const subjError = !subjectRef.current.value || subjectRef.current.length < 2;
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

    onAdd(recipientRef.current.value, subjectRef.current.value, message, () => onClose());

  }, [editorRef, recipientRef, setRecipientError, setMessageError, setSubjectError, subjectRef]);

  /**
   * Handles viewing the previous message
   * @function
   */
  const handlePrevMessage = React.useCallback(() => {
    if (curMessage && curMessageIndex > 0) {
      const curMsg = curMessage[curMessageIndex - 1];
      setCurMessageIndex(curMessageIndex - 1);
      setCurReadMessage(curMsg);
      setCurRecipient(curMsg.sender);
      setCurSubject(curMsg.subject);

      const readIndex = readMessageIds.findIndex((item) => item === curMsg.id);
      if (readIndex === -1) {
        readMessageIds.push(curMsg.id);
        onRead([curMsg.id]);
      }
    }
  }, [curMessageIndex, readMessageIds, setCurMessageIndex, setCurReadMessage]);

  /**
   * Handles viewing the next message
   * @function
   */
  const handleNextMessage = React.useCallback(() => {
    if (curMessage && curMessageIndex < curMessage.length - 1) {
      const curMsg = curMessage[curMessageIndex + 1];
      setCurMessageIndex(curMessageIndex + 1);
      setCurReadMessage(curMsg);
      setCurRecipient(curMsg.sender);
      setCurSubject(curMsg.subject);

      const readIndex = readMessageIds.findIndex((item) => item === curMsg.id);
      if (readIndex === -1) {
        readMessageIds.push(curMsg.id);
        onRead([curMsg.id]);
      }
    }
  }, [curMessageIndex, readMessageIds, setCurMessageIndex, setCurReadMessage]);

  // Return the UI
  return (
    <React.Fragment>
      <Grid id="new-message-wrapper" container direction="row" alignItems="center" justifyContent="center" 
            sx={{width:'100vw', height:'100vh', backgroundColor:'rgb(0,0,0,0.5)', position:'absolute', top:'0px', left:'0px', zIndex:2501}}
      >
        <Grid id="new-message-fields" container direction="column" style={{backgroundColor:'ghostwhite', border:'1px solid grey', borderRadius:'15px', padding:'25px 10px'}}>
          <TextField id='new-message-recepient'
                      required={readOnly ? false : true}
                      error={recipientError}
                      inputRef={recipientRef}
                      label={readOnly ? 'From' : 'To (comma seperated list of names. Send to admin to notify administrators)'}
                      disabled={readOnly}
                      fullWidth
                      size="small"
                      variant="standard"
                      value={curRecipient}
                      onChange={(event) => setCurRecipient(event.target.value)}
                      InputLabelProps={{
                        shrink: true, // Forces the label to move above the input
                      }}
                      sx={{marginBottom:'20px'}} />
          <TextField id='new-message-subject'
                      required={readOnly ? false : true}
                      error={subjectError}
                      inputRef={subjectRef}
                      label='Subject'
                      disabled={readOnly}
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
            onInit={(evt, editor) => editorRef.current = editor}
            initialValue={readOnly ? curReadMessage.message : undefined}
            disabled={readOnly}
            init={{
              promotion: false,
              branding: false,
              height: 200,
              menubar: false,
              elementpath: false,
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
            { readOnly && 
              <Grid container direction="row">
                <Button size="small" disabled={!curMessage || curMessage.length <= 1 || curMessageIndex === 0} onClick={handlePrevMessage}>&lt;</Button>
                <Typography variant="body2">{curMessageIndex + 1} of {curMessage ? curMessage.length : "?"}</Typography>
                <Button size="small" disabled={!curMessage || curMessage.length <= 1 || curMessageIndex === curMessage.length-1} onClick={handleNextMessage}>&gt;</Button>
              </Grid>
            }
            { !readOnly && <Button variant="contained" onClick={() => onSend()}>Send</Button> }
            <Button variant="contained" onClick={() => onClose()}>{readOnly ? "Done" : "Close"}</Button>
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
              <Grid container direction="column" alignItems="start" justifyContent="start" wrap="nowrap"
                      spacing={1}
                      sx={{paddingTop:'5px'}}
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
