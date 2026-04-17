'use client';

/** @module messages/ViewMessage */

import * as React from 'react';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import PropTypes from 'prop-types';

import { useTheme } from '@mui/material/styles';

/**
 * Displays a filtered list of usernames as a dropdown popup
 * @function
 * @param {string[]} filteredUsers List of usernames to display
 * @param {number} popupOffset Horizontal pixel offset to align popup with active segment
 * @param {function} onSelectUser Called with the selected username string
 * @returns {object|null} The popup UI, or null if no users to show
 */
export default function UserNames({ filteredUsers, popupOffset, onSelectUser }) {
  if (!filteredUsers || filteredUsers.length === 0) {
    return null;
  }

  return (
    <Paper
      elevation={3}
      sx={{
        position: 'absolute',
        top: '100%',
        left: `${popupOffset}px`,
        zIndex: 2600,
        maxHeight: '150px',
        overflowY: 'auto',
        minWidth: '150px',
      }}
    >
      {filteredUsers.map((name) => (
        <MenuItem
                key={name}
                onMouseDown={() => onSelectUser(name)}
                sx={{'&:hover': {
                        backgroundColor: 'primary.main',
                        color: 'primary.contrastText',
                      },
                  cursor: 'pointer',
                }}
        >
          {name}
        </MenuItem>
      ))}
    </Paper>
  );
}

UserNames.propTypes = {
  /** Filtered list of usernames to display in the popup */
  filteredUsers: PropTypes.arrayOf(PropTypes.string).isRequired,

  /** Horizontal pixel offset to position popup under the active segment */
  popupOffset: PropTypes.number,

  /** Called with the username string when a user selects an entry */
  onSelectUser: PropTypes.func.isRequired,
};

UserNames.defaultProps = {
  popupOffset: 0,
};