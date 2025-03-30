from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "Hello, this is a test endpoint!"})

@app.route('/sns-notifications', methods=['POST'])
def sns_test():
    print("SNS NOTIFICATION RECEIVED!")
    print(f"Headers: {dict(request.headers)}")
    try:
        raw_data = request.data.decode('utf-8')
        print(f"Raw Data: {raw_data[:500]}...")
    except Exception as e:
        print(f"Error decoding data: {str(e)}")
    
    return jsonify({"success": True, "message": "SNS notification received"})

@app.route('/api/sns/ses-notification', methods=['POST'])
def ses_notification():
    print("SES NOTIFICATION RECEIVED!")
    print(f"Headers: {dict(request.headers)}")
    try:
        raw_data = request.data.decode('utf-8')
        print(f"Raw Data: {raw_data[:500]}...")
    except Exception as e:
        print(f"Error decoding data: {str(e)}")
    
    return jsonify({"success": True, "message": "SES notification received"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
