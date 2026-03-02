'use client'

/** @module landing/FolderNewUpload */

import * as React from 'react';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import { SizeContext } from '../serverInfo';

/**
 * Returns the UI for ithe details of a new upload
 * @function
 * @param {number} stepNumber The step number to display
 * @param {number} stepTotal The total number of steps
 * @param {object} content The Card content to display
 * @param {object} actionInfo An array of button labels, onClick handlers, and disabled boolean values for each button
 * @returns {object} The rendered UI
 */
export default function FolderNewUpload({stepNumber, stepTotal, content, actionInfo}) {
  const theme = useTheme();
  const uiSizes = React.useContext(SizeContext);

  return (
    <Card id='folder-upload-details'  variant="outlined" sx={{ ...theme.palette.folder_upload, minWidth:uiSizes.workspace.width * 0.8 }} >
      <CardHeader sx={{ textAlign: 'center' }}
         title={
          <Typography gutterBottom variant="h6" component="h4">
            New Upload Details
          </Typography>
         }
         subheader={
          <React.Fragment>
            <Typography gutterBottom variant="body">
              Select Collection and Location to proceed
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
        {actionInfo?.map((item, idx) =>
          <Button key={idx} sx={{'flex':'1'}} size="small" onClick={item.onClick} disabled={item.disabled}>{item.label}</Button>
          )}
      </CardActions>
    </Card>
  );
}
