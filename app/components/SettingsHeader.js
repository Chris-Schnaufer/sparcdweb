/** @module components/SettingHeader */

import * as React from 'react';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

/**
 * Returns the UI for sortable column header
 * @function
 * @param {int} titleSize The size of the header columns
 * @param {string} title The title of the header
 * @param {object} titleStyle Additional styling for the title
 * @returns {object} The UI of the column header
 */
export default function SettingHeader() {
  const theme = useTheme();

/*  return(
      <Grid size={titleSize}>
        <Typography nowrap="true" variant="body" sx={titleStyle}>
          {title}
        </Typography>
      </Grid>
    );
*/
  return (null);
}
