# Protocol

## Request schema
```{json}
{
    "header": "fetch" | "publish" | "download" | "ping" | "sethost",
    "type": 0,
    "payload": {
        ...
    }
}
```

## Response schema
```{json}
{
    "header": "fetch" | "publish" | "download" | "ping" | "sethost",
    "type": 1,
    "payload": {
        "success": True | False,
        "message": string
        ...
    }
}
```

## Scenarios
### Set host
#### client -request-> server
```{json}
{
    "header": "sethost",
    "type": 0,
    "payload": {
        "hostname": string,
    }
}
```

#### server -response-> client
```{json}
{
    "header": "sethost",
    "type": 1,
    "payload": {
        "success": True | False,
        "message": string,
        "hostname": string,
        "address": string (client_address),
    }
}
```

### Publish
#### client -request-> server
```{json}
{
    "header": "publish",
    "type": 0,
    "payload": {
        "lname": string,
        "fname": string
    }
}
```
#### server -response-> client
```{json}
{
    "header": "publish",
    "type": 1,
    "payload": {
        "success": True | False,
        "message": string,
        "lname": string,
        "fname": string
    }
}
```

### Ping
#### server -request-> client
```{json}
{
    "header": "ping",
    "type": 0,
}
```
#### client -response-> server
```{json}
{
    "header": "ping",
    "type": 1,
    "payload": {
        "success": True | False,
        "message": string
    }
}
```

### Fetch
#### client -request-> server
```{json}
{
    "header": "fetch",
    "type": 0,
    "payload": {
        "fname": string
    }
}
```
#### server -response-> client
```{json}
{
    "header": "fetch",
    "type": 1,
    "payload": {
        "success": True | False,
        "message": string,
        "fname": string,
        "available_clients": [
            {
                "hostname": string,
                "address": string,
            },
            ...
        ]
    }
}
```

### Connect
#### client 1 -request-> client 2
```{json}
{
    "header": "download",
    "type": 0,
    "payload": {
        "fname": string (use file's name on server),
    }
}
```

#### client 2 -response-> client 1
```{json}
{
    "header": "download",
    "type": 1,
    "payload": {
        "success": True | False,
        "message": string,
        "length": int,
    }
}
```