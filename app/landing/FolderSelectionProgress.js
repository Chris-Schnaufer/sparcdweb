'use client'

/** @module landing/FolderSelectionProgress */

import * as React from 'react';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

/**
 * Returns the UI for starting an upload and when uploading files
 * @function
 * @param {string} type The type of upload for display
 * @param {string} subTitle The subtitle to display
 * @param {number} stepNumber The step number to display
 * @param {number} stepTotal The total number of steps
 * @param {object} content The Card content to display
 * @param {object} actions The Card Actions to render
 * @returns {object} The rendered UI
 */
export default function FolderSelectionProgress({type, subTitle, stepNumber, stepTotal, content, actions}) {
  const theme = useTheme();

  return (
    <Card id='folder-upload-select' variant="outlined" sx={{ ...theme.palette.folder_upload }} >
      <CardHeader sx={{ textAlign: 'center' }}
         title={
          <Typography gutterBottom variant="h6" component="h4">
            Upload {String(type).charAt(0).toUpperCase() + String(type).slice(1)} Folder
          </Typography>
         }
         subheader={
          <React.Fragment>
            <Typography gutterBottom variant="body">
              {subTitle}
            </Typography>
            <br />
            <Typography gutterBottom variant="body2">
              Step {stepNumber} of {stepTotal}
            </Typography>
          </React.Fragment>
          }
       />
      <CardContent>
        {content}
      </CardContent>
      <CardActions>
        {actions}
      </CardActions>
    </Card>

  );
}
