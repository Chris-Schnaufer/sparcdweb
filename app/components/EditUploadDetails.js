'use client'

/** @module components/EditUploadDetails */

import * as React from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';
import { useTheme } from '@mui/material/styles';

import PropTypes from 'prop-types';

import ModalDialog from '../components/ModalDialog';

/**
 * Returns the UI for editing an upload's details
 * @function
 * @param {object} upload The upload to edit
 * @param {function} onChange Call with the changes made to the upload
 * @param {function} onClose Call when the user wants to stop editing
 * @return {obect} The UI for editing an upload's details
 */
export default function EditUploadDetails({upload, onChange, onClose}) {
  const theme = useTheme();
  const [modified, setModified] = React.useState(false);
  const [description, setDescription] = React.useState(upload?.description ?? '');

  /**
   * Handles the description field changing 
   * @function
   * @param {object} event The triggering event
   */
  const handleDescriptionChange = React.useCallback((event) => {
    setDescription(event.target.value);
    setModified(true);
  }, []);

  /**
   * Prevents the dismissal of the dialog when clicking on the background
   * @function
   * @param {object} event The triggering event
   * @param {string} reason The reason for attempting the close
   */
  const handleClose = React.useCallback((event, reason) => {
      if (reason && reason === "backdropClick") 
          return;
      onClose();
  }, []);

  /**
   * Function to save the changes made
   * @function
   */
  const handleSave = React.useCallback(() => {
    onChange?.(upload, description,
          () => onClose()   // Success
    );
  }, [description, upload]);

  return (
    <ModalDialog id={'edit-upload-details-'+upload.key} backgroundColor="#D3DEE6" open={true} maxWidth='md' onClose={handleClose} >
      <DialogTitle>Edit Upload Details</DialogTitle>
      <DialogContent>
        <DialogContentText>
          {upload.name}
        </DialogContentText>
        <DialogContentText>
          <span style={{fontStyle:'italic'}}>Upload Folder:</span>&nbsp;{upload.folders.join(", ")}
        </DialogContentText>
          <TextField
            label="Description"
            value={description}
            onChange={handleDescriptionChange}
            fullWidth
            multiline
            rows={4}
            sx={{ mt: 2 }}
            autoFocus
          />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleSave} disabled={!modified}>Save</Button>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </ModalDialog>
  );
}

EditUploadDetails.propTypes = {
  upload: PropTypes.shape({
    key: PropTypes.string,
    name: PropTypes.string,
    description: PropTypes.string,
    folders: PropTypes.arrayOf(PropTypes.string),
  }),
  onChange: PropTypes.func,
  onClose: PropTypes.func.isRequired,
};
