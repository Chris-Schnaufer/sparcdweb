'use client';

/** @module components/UserMessages */

import * as React from 'react';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Checkbox from '@mui/material/Checkbox';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import ReplayOutlinedIcon from '@mui/icons-material/ReplayOutlined';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import { Level } from './Messages';
import NewUserMessage from './NewUserMessage';
import { AddMessageContext, TokenExpiredFuncContext, SizeContext, UserMessageContext } from '../serverInfo';

/**
 * Provides the UI for user messages
 * @function
 * @param {function} onAdd Called to add a new message
 * @param {function} onDelete Called to delelete messages
 * @param {function} onRefresh Called to refresh the messages
 * @param {function} onRead Called to mark messages as read
 * @param {function} onClose Called when the user is finished
 * @returns {object} The UI for managing messages
 */
export default function UserMessages({onAdd, onDelete, onRefresh, onRead, onClose}) {
  const MAX_MESSAGE_DISPLAY_LENGTH = 50
  const theme = useTheme();
  const addMessage = React.useContext(AddMessageContext); // Function adds messages for display
  const uiSizes = React.useContext(SizeContext);  // UI Dimensions
  const userMessages = React.useContext(UserMessageContext); // The user's messages
  const contentRef = React.useRef();
  const [allSelected, setAllSelected] = React.useState(false);  // When all messages are selected
  const [newMessage, setNewMessage] = React.useState(false);    // User wants to compose a message
  const [selectedMessages, setSelectedMessages] = React.useState([]); // The selected messages
  const [titlebarRect, setTitlebarRect] = React.useState(null); // Set when the UI displays

  // Recalcuate where to place ourselves
  React.useLayoutEffect(() => {
    calculateSizes();
  }, []);

  // Reposition ourselves on the center horizontally
  React.useLayoutEffect(() => {
    if (contentRef.current !== null) {
      const curRect = contentRef.current.getBoundingClientRect();
      const curOffsetX = (uiSizes.window.width / 2.0) - (curRect.width / 2.0);

      let el = document.getElementById('messages-wrapper');
      el.style.left = curOffsetX +'px';
      el.style.right = (curOffsetX + curRect.width) +'px';
    }
  }, [contentRef]);

  // Adds a resize handler to the window, and automatically removes it
  React.useEffect(() => {
      function onResize () {
        calculateSizes();
      }

      window.addEventListener("resize", onResize);
  
      return () => {
          window.removeEventListener("resize", onResize);
      }
  }, []);

  /**
   * Calculate some sizes and positions as needed
   * @function
   */
  function calculateSizes() {
    const titleEl = document.getElementsByTagName('header');
    if (titleEl) {
      const curRect = titleEl[0].getBoundingClientRect();
      setTitlebarRect(curRect);
      return curRect;
    }

    return null;
  }

  /**
   * Handles the user checking an individual checkbox
   * @function
   * @param {number} idx The index of the message to enable
   */
  function handleMessageChecked(event, idx) {
    const selIdx = selectedMessages.findIndex((item) => item === idx);
    if (event.target.checked) {
      // Add if not in there already
      if (selIdx == -1) {
        let curSel = selectedMessages;
        curSel.push(idx);
        setSelectedMessages([].concat(curSel));
      }
    } else {
      // Remove if not already removed
      if (selIdx !== -1) {
        setSelectedMessages(selectedMessages.splice(0, selIdx).concat(selectedMessages.splice(selIdx)));
      }
    }
  }

  /**
   * Handle all items selected or de-selected
   * @function
   */
  function handleAllSelected() {
    const curSelection = !allSelected;
    setAllSelected(curSelection);

    // Only update the selected messages if we have messages to load
    if (userMessages && !userMessages.loading && userMessages.messages) {
      // Select all messages
      if (curSelection === true) {
        const newSelection = [];
        for (let ii = 0; ii < userMessages.messages.length; ii++) {
          newSelection.push(ii);
        }
        setSelectedMessages(newSelection);
      } else {
        // Remove all selections
        setSelectedMessages([]);
      }
    }
  }

  /**
   * Generated a line for each message (or blank ones)
   * @function
   */
  function generateMessageLines() {
    // Check if we're still loading
    if (!userMessages || userMessages.loading === true) {
      return (
        <Grid id="messages-details-list" container direction="column" justifyContent="center" alignItems="center"
              sx={{width:'100%', minHeight:'360px', overflowY:"scroll"}}
              >
          <CircularProgress sx={{minWidth:'60px', minHeight:'60px'}} />
          <Typography variant="body2">
            Loading messages ...
          </Typography>
        </Grid>        
      )
    }

    // Come up with some filler if we need them
    const remainCount = userMessages && userMessages.messages ? (userMessages.messages.length > 15 ? 0 : 15 - userMessages.messages.length) : 15;
    return (
        <Grid id="messages-details-list" container direction="column" justifyContent="start" alignItems="center"
              rowSpacing={0} sx={{overflowY:"scroll", minHeight:'360px', width:'100%'}}
        >
        { userMessages && userMessages.messages && userMessages.messages.length > 0 &&
          userMessages.messages.map((item, idx) =>
            <Grid id={"message-details-" + idx} key={"message-details-" + idx} container direction="row" alignItems="center" justifyContent="start"
                  sx={{backgroundColor:read ? 'rgb(0, 0, 0, 0.07)' : 'transparent', borderBottom:'1px solid rgb(0, 0, 0, 0.07)', width:'100%', minHeight:'1.5em'}}
            >
              <Checkbox id={'message-'+idx} size="small" checked={selectedMessages.findIndex((item) => item === idx) !== -1}
                        onChange={(event) => handleMessageChecked(event, idx)}
              />
              <Typography variant="body2">
                {item.sender}
              </Typography>
              <Typography variant="body2">
                {item.subject}
              </Typography>
              <Typography variant="body2">
                {item.message.substring(0, MAX_MESSAGE_DISPLAY_LENGTH) + item.message.length > MAX_MESSAGE_DISPLAY_LENGTH ? '...' : ''}
              </Typography>
            </Grid>
          )
        }
        { [...Array(remainCount).keys()].map((item, idx) => 
            <Grid id={"message-details-" + idx} key={"message-details-" + idx} container direction="row" alignItems="center" justifyContent="start"
                  sx={{borderBottom:'1px solid rgb(0, 0, 0, 0.07)', width:'100%', minHeight:'1.5em'}}
            >
            </Grid>
          )
        }
        </Grid>
    );
  }

  /**
   * Generates the UI for messages
   * @function
   */
  function generateMessages() {
    return (
      <Grid id='messages-details-wrapper' container direction="column" justifyContent="start" alignItems="start"
            sx={{width:'100%', padding:'0px 5px 0 5px'}} >
        <Grid id='messages-details-toolbar' container direction="row" justifyContent="start" alignItems="center">
          <Tooltip title='Select'>
            <Checkbox id='messages-check-all' size="small" checked={allSelected} onChange={() => handleAllSelected()} />
          </Tooltip>
          <Tooltip title='Reload messages'>
            <IconButton aria-label="reload messages" size="small" onClick={onRefresh} >
              <ReplayOutlinedIcon size="small" />
            </IconButton>
          </Tooltip>
          <Button size="small" onClick={() => setNewMessage(true)} >Compose</Button>
        </Grid>
        {generateMessageLines()}
      </Grid>
    );
  }

  // Default the titlebar dimensions if it's not rendered yet
  let workingRect = titlebarRect;
  if (workingRect == null) {
    workingRect = calculateSizes();
    if (workingRect == null) {
      workingRect = {x:20,y:40,width:640};
    }
  }

  console.log('HACK: NEWMESSAGE',newMessage);
  return (
  <React.Fragment>
    <Grid id='messages-wrapper'
         sx={{position:'absolute', top:(workingRect.y+20)+'px', right:'20px', zIndex:2500}}
    >
      <Card id="messages-content" ref={contentRef} sx={{minWidth:'400px', backgroundColor:'ghostwhite', border:'1px solid lightgrey', borderRadius:'20px'}} >
        <CardHeader title="Manage Messages" />
        <CardContent sx={{paddingTop:'0px', paddingBottom:'0px'}}>
          <Grid container direction="column" alignItems="start" justifyContent="start" wrap="nowrap"
                  spacing={1}
                  sx={{overflowY:'scroll', paddingTop:'5px'}}
          >
          {generateMessages()}
          </Grid>
        </CardContent>
        <CardActions>
          <Grid container id="settings-actions-wrapper" direction="row" sx={{justifyContent:'center', alignItems:'center', width:'100%'}}
          >
            <Button variant="contained" onClick={() => onClose()}>Close</Button>
          </Grid>
        </CardActions>
      </Card>
    </Grid>
    { newMessage && <NewUserMessage onAdd={onAdd} onClose={() => setNewMessage(false)} />}
  </React.Fragment>
  )
}
