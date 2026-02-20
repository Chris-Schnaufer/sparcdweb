'use client';

/** @module components/NewUserMessage */

import * as React from 'react';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import { useTheme } from '@mui/material/styles';

/**
 * Provides the UI for a new user message
 * @function
 * @param {function} onAdd Called to add a new message
 * @param {function} onClose Called when the user is finished
 * @returns {object} The UI for managing messages
 */
export default function NewUserMessage({onAdd, onClose}) {
  const theme = useTheme();

  // Return the UI
  return (
      <Grid id="new-message-wrapper" container direction="row" alignItems="center" justifyContent="center" 
            sx={{width:'100vw', height:'100vh', backgroundColor:'rgb(0,0,0,0.5)', position:'absolute', top:'0px', left:'0px', zIndex:2501}}
      >
        <div style={{backgroundColor:'ghostwhite', border:'1px solid grey', borderRadius:'15px', padding:'25px 10px'}}>
          <Grid container direction="column" alignItems="center" justifyContent="center" >
            <Button variant="contained" onClick={() => onClose()}>Close</Button>
          </Grid>
        </div>
      </Grid>
  );
}
