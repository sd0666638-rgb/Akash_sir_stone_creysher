import { IconButton, InputAdornment, TextField, Tooltip } from "@mui/material";
import { CalendarDays } from "lucide-react";

import { localDateText } from "../utils/date.js";

export default function TodayDateField({
  InputLabelProps,
  InputProps,
  inputProps,
  label,
  onToday,
  size,
  ...textFieldProps
}) {
  const todayLabel =
    typeof label === "string" && label ? `Set ${label.toLowerCase()} to today` : "Set date to today";

  return (
    <TextField
      {...textFieldProps}
      label={label}
      type="date"
      size={size}
      InputLabelProps={{ ...InputLabelProps, shrink: true }}
      inputProps={inputProps}
      InputProps={{
        ...InputProps,
        endAdornment: (
          <>
            {InputProps?.endAdornment}
            <InputAdornment position="end" sx={{ ml: 0.25, mr: -0.5 }}>
              <Tooltip title="Today">
                <span>
                  <IconButton
                    type="button"
                    size="small"
                    aria-label={todayLabel}
                    disabled={Boolean(textFieldProps.disabled || inputProps?.readOnly)}
                    onClick={() => onToday?.(localDateText())}
                  >
                    <CalendarDays size={size === "small" ? 16 : 18} />
                  </IconButton>
                </span>
              </Tooltip>
            </InputAdornment>
          </>
        ),
      }}
    />
  );
}
