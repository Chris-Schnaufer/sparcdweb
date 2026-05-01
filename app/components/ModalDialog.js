'use client'

/** @module components/ModelDialog */

import * as React from 'react';
import Dialog from '@mui/material/Dialog';
import { useTheme } from '@mui/material/styles';

import PropTypes from 'prop-types';

const DEFAULT_DIALOG_ZINDEX = 10000

/**
 * Implementation of a modal dialog
 * @function
 * @param {string} [backgroundColor] The background color of the dialog
 * @param {object} [extraSx] Additional dialog sx
 * @param {boolean} [open] Whether the dialog is open. Defaults to true if not specified
 * @param {string} [maxWidth] The maximum width of the dialog
 * @param {function} onClose Callback when the dialog is closed
 * @param {React.ReactNode} children The children elements of the dialog
 * @returns {object} Returns the modal dialog UI
 */
export default function ModalDialog({ backgroundColor, extraSx, open, maxWidth, onClose, children }) {
  const theme = useTheme();

  const isOpen = open ?? true;

  return (
    <Dialog open={isOpen} onClose={onClose} maxWidth={maxWidth ? maxWidth: "md"} fullWidth
      sx={{"& .MuiPaper-root": {borderRadius: '25px', ...(backgroundColor && { backgroundColor }) },
            zIndex: `calc(var(--parent-z-index, ${DEFAULT_DIALOG_ZINDEX}) + 1000)`,
            ...extraSx}}
    >
      {children}
    </Dialog>
  );
}

ModalDialog.propTypes = {
  backgroundColor: PropTypes.string,
  extraSx: PropTypes.object,
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  children: PropTypes.node.isRequired,
};
